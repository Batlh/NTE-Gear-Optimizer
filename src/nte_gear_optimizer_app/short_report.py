"""Small default report, preserving every retained error and the last300events."""

from copy import deepcopy
import json

from .debug_journal import JSON_MARKER, PRIVACY_NOTICE

GUIDE_FIELDS = {
    'StatID',
    'Unit',
    'TargetMinimum',
    'TargetMaximum',
    'BeforeAligned',
    'AfterAligned',
    'RawDelta',
    'Trend',
    'ReferenceUnavailableReason',
    'BeforeAttained',
    'AfterAttained',
    'StatusChange',
}


def brief_result(value):
    if not isinstance(value, dict):
        return value
    value = deepcopy(value)
    if isinstance(value.get('engine'), dict):
        engine = value['engine']
        if isinstance(engine.get('GuideReferenceBlock'), list):
            engine['GuideReferenceBlock'] = [
                {k: v for k, v in row.items() if k in GUIDE_FIELDS}
                for row in engine['GuideReferenceBlock']
            ]
    if 'guide' in value:
        raw = value.pop('guide')
        value['raw_guide_detail'] = (
            'Full provenance rows in the complete report; '
            + str(len(raw))
            + 'entries omitted here.'
        )
    return value


def brief_event(row):
    row = deepcopy(row)
    row.pop('utc', None)  # monotone ms + session + sequence remain on every row
    if 'result' in row:
        row['result'] = brief_result(row['result'])
    widget = row.get('widget')
    if isinstance(widget, dict):
        row['widget'] = {
            k: v
            for k, v in widget.items()
            if k not in ('depth', 'uid', 'in_white_subtree')
        }
    return row


def readable_event(row):
    fields = {
        k: row[k]
        for k in (
            'field',
            'raw',
            'normalized',
            'hint',
            'step',
            'selector',
            'new_id',
            'mode',
            'operation',
            'duration_ms',
            'position',
        )
        if k in row
    }
    if isinstance(row.get('widget'), dict):
        w = row['widget']
        fields['target'] = w.get('field') or w.get('label') or w.get('class')
    if isinstance(row.get('result'), dict):
        fields['result'] = {
            k: row['result'].get('engine', {}).get(k)
            for k in ('Verdict', 'VerdictRatio', 'OutputStatus')
        }
    return (
        '#'
        + str(row.get('seq'))
        + ' +'
        + str(row.get('ms'))
        + 'ms '
        + str(row.get('event'))
        + ' '
        + json.dumps(fields, ensure_ascii=False, separators=(',', ':'))
    )


def render_short_report(payload):
    rows = payload['events']
    errors = [
        row
        for row in rows
        if row.get('event') in ('exception', 'journal_storage_error')
        or row.get('stacktrace')
    ]
    value = {
        **payload,
        'report_mode': 'SHORT',
        'events': [brief_event(row) for row in rows[-300:]],
        'errors': errors,
        'retained_events_before_shortening': len(rows),
    }
    value['state'] = deepcopy(payload['state'])
    if 'result' in value['state']:
        value['state']['result'] = brief_result(value['state']['result'])
    scroll = value['state'].get('scroll_summary')
    if isinstance(scroll, dict) and isinstance(scroll.get('gestures'), list):
        scroll['gestures'] = scroll['gestures'][-10:]
        scroll['detail_scope'] = (
            'Latest10gesture details; aggregate count/median from retained100.'
        )
    heading = [
        'NTE Gear Optimizer – Kurzbericht',
        PRIVACY_NOTICE,
        'Zeitangaben in Millisekunden. Vollständige Details bei Bedarf über „Vollständig“.',
        json.dumps(value['device'], ensure_ascii=False),
        'Langsamste10Vorgänge (>100ms: LANGSAM):',
    ]
    heading.extend(
        ('LANGSAM | ' if row.get('over_100_ms') else '')
        + str(row['operation'])
        + ': '
        + str(row['duration_ms'])
        + ' ms'
        for row in value['performance_summary']['slowest_10']
    )
    heading += [
        'Scroll-Zusammenfassung:',
        json.dumps(
            value['state'].get('scroll_summary', {}),
            ensure_ascii=False,
            separators=(',', ':'),
        ),
        'Aktueller Zustand:',
        json.dumps(value['state'], ensure_ascii=False, separators=(',', ':')),
        'Alle Fehler aus dem erhaltenen Protokoll:',
    ]
    heading.extend(
        json.dumps(row, ensure_ascii=False, separators=(',', ':')) for row in errors
    )
    heading += ['Letzte300Ereignisse (oder weniger):']
    heading.extend(readable_event(row) for row in value['events'])
    return (
        '\n'.join(heading)
        + JSON_MARKER
        + json.dumps(value, ensure_ascii=False, separators=(',', ':'))
        + '\n'
    )
