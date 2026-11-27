import json
from pathlib import Path

from nte_gear_optimizer_app.debug_journal import (
    DebugJournal,
    JSON_MARKER,
    PRIVACY_NOTICE,
)


def test_coalescing_blur_and_order(tmp_path):
    now = [0.0]
    log = DebugJournal(tmp_path, clock=lambda: now[0])
    log.input('a', '1', '1', '')
    now[0] = 0.3
    log.input('a', '12', '12', '')
    now[0] = 0.7
    log.flush_inputs()
    assert [r['event'] for r in log.events()] == ['session_start']
    now[0] = 0.81
    log.flush_inputs()
    log.input('b', '2,5', '2.5', '')
    log.flush_inputs('b', force=True)
    rows = log.events()
    assert [r['seq'] for r in rows] == [1, 2, 3]
    assert rows[1]['raw'] == '12' and rows[2]['normalized'] == '2.5'


def test_rotation_durability_and_prior_session(tmp_path):
    log = DebugJournal(tmp_path, max_bytes=1024)
    for i in range(100):
        log.emit('touch', value=i)
    files = list(tmp_path.iterdir())
    assert len(files) <= 3
    assert all(p.stat().st_size <= 1024 for p in files)
    previous = log.session
    other = DebugJournal(tmp_path, max_bytes=1024)
    assert {r['session'] for r in other.events()} == {previous, other.session}
    assert other.events()[-1]['event'] == 'session_start'


def test_exception_chain_and_report_privacy_roundtrip(tmp_path):
    log = DebugJournal(tmp_path)
    try:
        try:
            raise ValueError('Umlaute äöüß – Kiwi 🥝')
        except ValueError as root:
            raise OSError('Unable to read C:\\Users\\PrivateName\\other.txt') from root
    except OSError as error:
        log.exception(error, caught=True)
    report = log.report(
        {'model': 'emulator', 'account': 'forbidden', 'custom_name': 'forbidden'},
        {'raw': '2 560', 'normalized': '2560'},
    )
    payload = json.loads(report.split(JSON_MARKER)[1])
    assert payload['device'] == {'model': 'emulator'}
    assert payload['state']['raw'] == '2 560'
    trace = next(
        r['stacktrace'] for r in payload['events'] if r['event'] == 'exception'
    )
    assert 'ValueError' in trace and 'OSError' in trace and 'äöüß – Kiwi 🥝' in trace
    assert 'PrivateName' not in report and str(Path(__file__).parent) not in report
    assert PRIVACY_NOTICE in report


def test_logging_failure_does_not_raise(tmp_path):
    blocker = tmp_path / 'file'
    blocker.write_text('not a directory', encoding='utf-8', newline='\n')
    log = DebugJournal(blocker)
    assert log.failed
    log.emit('result', verdict='BETTER')
    assert 'BETTER' in log.report({}, {})


def test_clear_requires_confirmation(tmp_path):
    log = DebugJournal(tmp_path)
    original = log.events()
    assert log.clear() is False
    assert log.events() == original
    assert log.clear(confirmed=True)
    assert [r['event'] for r in log.events()] == ['logs_cleared_by_user']


def test_large_user_input_is_bounded(tmp_path):
    log = DebugJournal(tmp_path, max_bytes=1024)
    log.emit('input', raw='a' * 100_000)
    assert all(p.stat().st_size <= 1024 for p in tmp_path.iterdir())
    assert log.events()[-1]['data_truncated'] is True
