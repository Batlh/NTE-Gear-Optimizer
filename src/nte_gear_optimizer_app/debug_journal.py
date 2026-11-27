"""Bounded, offline diagnostic journal. Failure never changes application state."""

from collections import deque
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import threading
import time
import traceback
import uuid

PRIVACY_NOTICE = (
    'Der Bericht enthält deine eingegebenen Spielwerte und technische Gerätedaten, '
    'aber keine weiteren persönlichen Daten.'
)
JSON_MARKER = '\n--- NTE_DEBUG_JSON ---\n'
DEVICE_FIELDS = {
    'app_version',
    'commit',
    'version_code',
    'platform',
    'android_version',
    'model',
    'screen',
    'density',
    'ime',
}


def private_log_directory(platform, android_files=None):
    if platform == 'android':
        if android_files is None:
            raise ValueError('Android internal files directory required')
        return Path(android_files) / 'nte_debug' / 'logs'
    if platform == 'win':
        return Path(os.environ['LOCALAPPDATA']) / 'NTEGearOptimizer' / 'logs'
    if platform == 'macosx':
        return (
            Path.home()
            / 'Library'
            / 'Application Support'
            / 'NTEGearOptimizer'
            / 'logs'
        )
    return (
        Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state'))
        / 'nte_gear_optimizer'
        / 'logs'
    )


def private_text(text):
    # Retain frame filename/function/line and the full exception chain, never
    # external absolute path prefixes or user-directory names. Game input has
    # no valid path syntax; apply the same rule to pasted input and OSErrors.
    value = str(text)
    value = re.sub(r'(?i)[a-z]:[\\/][^\s"\'<>]+', '<external-path>', value)
    value = re.sub(
        r'(?<![\w:])/(?:[^/\s"\'<>]+/)+[^\s"\'<>]*', '<external-path>', value
    )
    return value


def clean(value):
    if isinstance(value, str):
        return private_text(value)
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return private_text(value)


class DebugJournal:
    def __init__(
        self, directory, *, max_bytes=512 * 1024, slots=3, clock=time.monotonic
    ):
        self.directory = Path(directory)
        self.max_bytes = max_bytes
        self.slots = slots
        self.clock = clock
        self.start = clock()
        self.session = uuid.uuid4().hex
        self.seq = 0
        self.lock = threading.RLock()
        self.pending = {}
        self.recent = deque(maxlen=200)
        self.failed = False
        self.last_sync = float('-inf')
        self._begin_session()
        self.emit('session_start')

    def _begin_session(self):
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            lines = []
            for index in reversed(range(self.slots - 1)):
                path = self._file(index)
                if path.exists():
                    lines.extend(path.read_bytes().splitlines(keepends=True))
            if lines:
                selected = []
                size = 0
                for line in reversed(lines):
                    if size + len(line) > self.max_bytes:
                        break
                    selected.append(line)
                    size += len(line)
                with self._file(self.slots - 1).open('wb') as previous:
                    previous.write(b''.join(reversed(selected)))
                for index in range(self.slots - 1):
                    self._file(index).unlink(missing_ok=True)
        except Exception:
            self.failed = True

    def _file(self, index):
        return self.directory / f'events_{index}.jsonl'

    def emit(self, event, **data):
        try:
            with self.lock:
                self.seq += 1
                row = clean(
                    {
                        'session': self.session,
                        'seq': self.seq,
                        'ms': round((self.clock() - self.start) * 1000),
                        'utc': datetime.now(timezone.utc).isoformat(
                            timespec='milliseconds'
                        ),
                        'event': event,
                        **data,
                    }
                )
                line = (
                    json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n'
                ).encode('utf-8')
                if len(line) > self.max_bytes:
                    # Text pasted by a user must not grow the log without bound.
                    row = {**row, 'data_truncated': True}
                    row = {
                        k: (v[:2000] if isinstance(v, str) else v)
                        for k, v in row.items()
                    }
                    line = (json.dumps(row, ensure_ascii=False) + '\n').encode('utf-8')
                    if len(line) > self.max_bytes:
                        row = {
                            k: row[k] for k in ('session', 'seq', 'ms', 'utc', 'event')
                        }
                        row['data_truncated'] = True
                        line = (json.dumps(row) + '\n').encode('utf-8')
                self.recent.append(row)
                self.directory.mkdir(parents=True, exist_ok=True)
                active = self._file(0)
                if (
                    active.exists()
                    and active.stat().st_size + len(line) > self.max_bytes
                ):
                    for i in range(self.slots - 2, 0, -1):
                        previous = self._file(i - 1)
                        if previous.exists():
                            previous.replace(self._file(i))
                with active.open('ab') as f:
                    f.write(line)
                    f.flush()
                    if self.clock() - self.last_sync >= 0.5 or event in (
                        'exception',
                        'app_stop',
                        'app_pause',
                        'session_start',
                    ):
                        os.fsync(f.fileno())
                        self.last_sync = self.clock()
                return row
        except Exception:
            self.failed = True
            return None

    def input(self, field, raw, normalized, hint):
        try:
            with self.lock:
                self.pending[field] = (
                    self.clock(),
                    {
                        'field': field,
                        'raw': raw,
                        'normalized': normalized,
                        'hint': hint,
                    },
                )
        except Exception:
            self.failed = True

    def flush_inputs(self, field=None, *, force=False):
        try:
            with self.lock:
                for key, (stamp, data) in list(self.pending.items()):
                    if (field is None or key == field) and (
                        force or self.clock() - stamp >= 0.5
                    ):
                        self.pending.pop(key)
                        self.emit('input', **data)
        except Exception:
            self.failed = True

    def exception(self, error, *, caught):
        # TracebackException.format keeps chained exceptions and all frames.
        frames = traceback.TracebackException.from_exception(error)

        def private_frames(node):
            if node is None:
                return
            for frame in node.stack:
                frame.filename = Path(frame.filename.replace('\\', '/')).name
            private_frames(node.__cause__)
            private_frames(node.__context__)
            for child in getattr(node, 'exceptions', None) or []:
                private_frames(child)

        private_frames(frames)
        self.emit(
            'exception',
            caught=caught,
            exception_type=type(error).__name__,
            stacktrace=''.join(frames.format()),
        )

    def events(self):
        rows = []
        try:
            with self.lock:
                for index in reversed(range(self.slots)):
                    path = self._file(index)
                    if path.exists():
                        for line in path.read_text(encoding='utf-8').splitlines():
                            try:
                                rows.append(json.loads(line))
                            except ValueError, TypeError:
                                continue
        except Exception:
            rows = list(self.recent)
        if self.failed:
            existing = {(r.get('session'), r.get('seq')) for r in rows}
            rows.extend(
                r
                for r in self.recent
                if (r.get('session'), r.get('seq')) not in existing
            )
        return rows

    def report(self, device, state):
        self.flush_inputs(force=True)
        payload = clean(
            {
                'format': 'NTE_DEBUG_V1',
                'privacy_notice': PRIVACY_NOTICE,
                'device': {k: v for k, v in device.items() if k in DEVICE_FIELDS},
                'state': state,
                'events': self.events(),
                'storage_failed': self.failed,
            }
        )
        completed = [
            row
            for row in payload['events']
            if row.get('event') == 'performance'
            and isinstance(row.get('duration_ms'), (int, float))
        ]
        payload['performance_summary'] = {
            'slowest_10': sorted(
                completed, key=lambda row: row['duration_ms'], reverse=True
            )[:10],
            'completed_count_in_retained_log': len(completed),
            'over_100_ms_count': sum(
                row.get('over_100_ms') is True for row in completed
            ),
            'scope': 'Retained current/prior session only. GL surface flip is a presentation proxy, not physical display latency. The currently running export finishes after its file is generated; its completed duration is available in the next report.',
        }
        heading = ['NTE Gear Optimizer – Debugbericht', PRIVACY_NOTICE]
        heading += [
            f'{key}: {json.dumps(value, ensure_ascii=False)}'
            for key, value in payload['device'].items()
        ]
        heading += [
            '',
            'Dauern in Millisekunden – langsamste 10 abgeschlossene Vorgänge:',
            'Über 100 ms: LANGSAM. Nur Messungen, keine automatische Optimierung.',
            'Touch: ab Zustellung an die App bis zum ersten GL-Bildwechsel nach bekannter Reaktion; keine Messung der physischen Anzeige.',
            'Der laufende Export ist erst im nächsten Bericht vollständig messbar.',
        ]
        heading += [
            ('LANGSAM | ' if row.get('over_100_ms') else '')
            + str(row.get('operation'))
            + ': '
            + str(row['duration_ms'])
            + ' ms'
            + ' | '
            + json.dumps(
                {
                    key: row[key]
                    for key in ('step', 'selector', 'mode', 'endpoint', 'reaction')
                    if key in row
                },
                ensure_ascii=False,
            )
            for row in payload['performance_summary']['slowest_10']
        ]
        heading += [
            '',
            'Aktueller Zustand:',
            json.dumps(payload['state'], ensure_ascii=False, indent=2),
            '',
            'Ablauf (älteste Einträge zuerst):',
        ]
        heading += [json.dumps(row, ensure_ascii=False) for row in payload['events']]
        return (
            '\n'.join(heading)
            + JSON_MARKER
            + json.dumps(payload, ensure_ascii=False, indent=2)
            + '\n'
        )

    @staticmethod
    def filename():
        return datetime.now().strftime('NTE_Debugbericht_%Y%m%d_%H%M%S_%f.txt')

    def clear(self, *, confirmed=False):
        if not confirmed:
            return False
        try:
            with self.lock:
                for i in range(self.slots):
                    self._file(i).unlink(missing_ok=True)
                self.pending.clear()
                self.recent.clear()
                self.emit('logs_cleared_by_user')
            return True
        except Exception:
            self.failed = True
            return False


def install_uncaught_hooks(journal):
    previous = sys.excepthook

    def exception_hook(kind, error, tb):
        journal.exception(error, caught=False)
        previous(kind, error, tb)

    sys.excepthook = exception_hook
    previous_thread = threading.excepthook

    def thread_hook(args):
        journal.exception(args.exc_value, caught=False)
        previous_thread(args)

    threading.excepthook = thread_hook
