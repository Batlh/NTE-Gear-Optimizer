import json

from nte_gear_optimizer_app.debug_journal import DebugJournal, JSON_MARKER


def test_storage_failure_keeps_error_cause_in_memory_without_raising(tmp_path):
    blocker = tmp_path / 'not_a_directory'
    blocker.write_text('fixture', encoding='utf-8', newline='\n')
    journal = DebugJournal(blocker)
    journal.emit('result', verdict='BETTER')
    payload = json.loads(journal.report({}, {}).split(JSON_MARKER)[1])
    errors = [
        row for row in payload['events'] if row['event'] == 'journal_storage_error'
    ]
    assert errors, (
        'Logging failure must retain its cause when memory reporting is still possible'
    )
    assert errors[0]['exception_type'] in {'FileExistsError', 'NotADirectoryError'}
    assert 'Traceback' in errors[0]['stacktrace']
    assert str(tmp_path) not in payload['events'][0].get('stacktrace', '')
    assert any(row.get('verdict') == 'BETTER' for row in payload['events'])


def test_public_sources_are_not_filesystem_paths(tmp_path):
    journal = DebugJournal(tmp_path)
    url = 'https://www.prydwen.gg/neverness-to-everness/characters/adler'
    report = journal.report(
        {},
        {
            'Source': url,
            'external': 'C:\\Users\\PrivatePerson\\outside.txt',
            'unc': r'\\PrivateServer\PrivatePerson\outside.txt',
        },
    )
    payload = json.loads(report.split(JSON_MARKER)[1])
    assert payload['state']['Source'] == url
    assert 'PrivatePerson' not in report
    assert 'PrivateServer' not in report


def test_recovered_disk_and_memory_records_remain_chronological(tmp_path, monkeypatch):
    from nte_gear_optimizer_app import debug_journal as module

    now = [0.0]
    journal = DebugJournal(tmp_path, clock=lambda: now[0])
    original = module.os.fsync

    def unavailable(fd):
        raise OSError('fixture fsync unavailable')

    monkeypatch.setattr(module.os, 'fsync', unavailable)
    now[0] = 1.0
    journal.emit('first', value=1)
    monkeypatch.setattr(module.os, 'fsync', original)
    now[0] = 2.0
    journal.emit('second', value=2)
    rows = journal.events()
    sequences = [r['seq'] for r in rows if r['session'] == journal.session]
    assert sequences == sorted(set(sequences))
    assert any(r['event'] == 'journal_storage_error' for r in rows)
