import json
from nte_gear_optimizer_app.debug_journal import DebugJournal, JSON_MARKER
from nte_gear_optimizer_app.short_report import render_short_report


def test_default_brief_preserves_old_errors_last300_and_raw_values(tmp_path):
    log = DebugJournal(tmp_path)
    try:
        raise ValueError('Expected test exception – äöüß')
    except ValueError as e:
        log.exception(e, caught=True)
    for i in range(600):
        log.emit('input', raw=str(i), normalized=str(i), field='x:UniversalPP')
    full = json.loads(
        log.report({}, {'inputs': [{'raw': '2,5', 'normalized': '2.5'}]}).split(
            JSON_MARKER
        )[1]
    )
    text = render_short_report(full)
    payload = json.loads(text.split(JSON_MARKER)[1])
    assert payload['report_mode'] == 'SHORT'
    assert len(payload['events']) == 300
    assert (
        payload['events'][0]['raw'] == '300' and payload['events'][-1]['raw'] == '599'
    )
    assert (
        len(payload['errors']) == 1
        and 'ValueError' in payload['errors'][0]['stacktrace']
    )
    assert payload['state']['inputs'][0]['raw'] == '2,5'
    assert len(text.encode('utf-8')) < 200_000


def test_real_2a3_example_is_under200k_without_erasing_error():
    # Fixture shape models the real excess: duplicated raw guide provenance.
    payload = {
        'format': 'NTE_DEBUG_V1',
        'privacy_notice': 'notice',
        'device': {'model': 'test'},
        'state': {},
        'performance_summary': {'slowest_10': []},
        'storage_failed': False,
        'events': [],
    }
    result = {
        'engine': {
            'Verdict': None,
            'OutputStatus': 'INDETERMINATE_MISSING_DEPENDENCY',
            'GuideReferenceBlock': [
                {'StatID': 'STAT_ATK', 'RawDelta': '10', 'SourceDetail': 'x' * 20_000}
                for _ in range(20)
            ],
        },
        'guide': [{'raw': 'x' * 20000} for _ in range(20)],
        'part_deltas': {'ScaleDirect': '10'},
        'errors': {},
    }
    payload['state']['result'] = result
    payload['events'] = [
        {'seq': i, 'ms': i, 'event': 'result', 'result': result} for i in range(3)
    ]
    payload['events'] += [
        {
            'seq': i,
            'ms': i,
            'event': 'touch_accepted',
            'widget': {
                'class': 'TextInput',
                'field': 'y:ScaleDirect',
                'rect': [0, 0, 50, 50],
            },
        }
        for i in range(3, 300)
    ]
    text = render_short_report(payload)
    data = json.loads(text.split(JSON_MARKER)[1])
    assert (
        data['state']['result']['engine']['OutputStatus']
        == 'INDETERMINATE_MISSING_DEPENDENCY'
    )
    assert data['state']['result']['part_deltas']['ScaleDirect'] == '10'
    assert len(text.encode('utf-8')) < 200_000
