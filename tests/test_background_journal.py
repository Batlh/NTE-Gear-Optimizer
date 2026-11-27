from pathlib import Path
import json
import threading
from nte_gear_optimizer_app.background_journal import BackgroundJournal
from nte_gear_optimizer_app.debug_journal import DebugJournal, JSON_MARKER


def test_io_is_exclusively_on_worker_with_barrier(tmp_path, monkeypatch):
    original = Path.open
    observed = []

    def tracked(path, *args, **kwargs):
        if path.is_relative_to(tmp_path):
            observed.append(threading.current_thread().name)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'open', tracked)
    log = BackgroundJournal(tmp_path)
    try:
        for i in range(60):
            log.emit('field', raw=str(i))
        log.barrier()
        report = log.report({}, {'raw': 'äöüß – 🥝'})
        payload = json.loads(report.split(JSON_MARKER)[1])
        assert payload['events'][-1]['raw'] == '59'
        assert all(name == 'NTE-debug-writer' for name in observed)
        assert observed
    finally:
        log.close()


def test_slow_disk_does_not_block_emit_or_mutate_snapshot(tmp_path):
    gate = threading.Event()

    class Slow(DebugJournal):
        def __init__(self, *a, **k):
            assert gate.wait(3)
            super().__init__(*a, **k)

    log = BackgroundJournal(tmp_path, store_factory=Slow)
    value = {'raw': '1'}
    assert log.emit('input', value=value)
    value['raw'] = '2'
    gate.set()
    try:
        assert log.events()[-1]['value']['raw'] == '1'
        assert log.clear() is False
        assert log.clear(confirmed=True)
        assert log.events()[-1]['event'] == 'logs_cleared_by_user'
    finally:
        log.close()


def test_queue_is_bounded_and_diagnostic_failure_never_raises(tmp_path):
    gate = threading.Event()

    class Slow(DebugJournal):
        def __init__(self, *a, **k):
            assert gate.wait(3)
            super().__init__(*a, **k)

    log = BackgroundJournal(tmp_path, capacity=2, store_factory=Slow)
    for i in range(20):
        log.emit('touch', index=i)
    assert log.dropped and log.failed
    gate.set()
    log.close()
