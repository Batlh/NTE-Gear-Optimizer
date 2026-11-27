import json
from types import SimpleNamespace

import pytest

from nte_gear_optimizer_app.performance import PerformanceTrace, timed
from nte_gear_optimizer_app.debug_journal import DebugJournal, JSON_MARKER


def test_milliseconds_threshold_and_frame_endpoint():
    now = [0.0]
    rows = []
    trace = PerformanceTrace(
        lambda event, **row: rows.append({'event': event, **row}), clock=lambda: now[0]
    )
    token = trace.start('render', step=1)
    now[0] = 0.125
    trace.finish(token, frame=True)
    assert rows[0]['duration_ms'] == 125
    assert rows[0]['over_100_ms'] is True
    assert rows[0]['step'] == 1
    now[0] = 0.140
    trace.frame()
    assert rows[1]['operation'] == 'render_first_frame'
    assert rows[1]['duration_ms'] == 140
    assert rows[1]['endpoint'] == 'Window.on_flip_proxy'
    trace.frame()
    assert len(rows) == 2


def test_touch_requires_observed_reaction_not_arbitrary_frame():
    now = [0.0]
    rows = []
    trace = PerformanceTrace(
        lambda event, **row: rows.append(row), clock=lambda: now[0]
    )
    trace.touch_begin('42')
    now[0] = 0.02
    trace.frame()
    assert not rows
    trace.response('button_pressed', '42')
    now[0] = 0.05
    trace.frame()
    assert rows[0]['operation'] == 'touch_to_response_frame'
    assert rows[0]['duration_ms'] == 50
    assert rows[0]['touch_id'] == '42'
    assert rows[0]['over_100_ms'] is False
    trace.response('focus', '42')
    trace.frame()
    assert len(rows) == 1


def test_pending_measurements_are_bounded_and_expired_not_guessed():
    now = [0.0]
    rows = []
    trace = PerformanceTrace(
        lambda event, **row: rows.append(row), clock=lambda: now[0]
    )
    for i in range(100):
        trace.touch_begin(str(i))
    assert len(trace.touches) == 32
    now[0] = 6
    trace.response('focus')
    trace.frame()
    assert not rows
    token = trace.start('export', mode='share')
    assert trace.in_progress()[0]['complete'] is False
    trace.finish(token)
    assert not trace.in_progress()


def test_timing_observer_does_not_change_result_or_exception():
    class Example:
        step = 2
        performance = PerformanceTrace(lambda *a, **k: None)

        @timed('calculate')
        def calculate(self, value):
            return value

        @timed('calculate')
        def fail(self):
            raise ValueError('original')

    subject = Example()
    original = {'Verdict': 'BETTER', 'RawRatio': '1.2'}
    assert subject.calculate(original) is original
    with pytest.raises(ValueError, match='original'):
        subject.fail()
    subject.performance = SimpleNamespace(
        start=lambda *a, **k: 1,
        finish=lambda *a, **k: (_ for _ in ()).throw(OSError('sink')),
    )
    assert subject.calculate(original) is original
    subject.performance = None
    assert subject.calculate(original) is original


def test_top10_report_and_export_completion_causality(tmp_path):
    log = DebugJournal(tmp_path)
    now = [0.0]
    trace = PerformanceTrace(log.emit, clock=lambda: now[0])
    for i in range(12):
        token = trace.start('selector_build', selector=str(i), step=1)
        now[0] += (i + 1) / 100
        trace.finish(token)
    export = trace.start('export', mode='share')
    initial = json.loads(
        log.report({}, {'timing_in_progress': trace.in_progress()}).split(JSON_MARKER)[
            1
        ]
    )
    assert initial['state']['timing_in_progress'][0]['operation'] == 'export'
    assert initial['state']['timing_in_progress'][0]['complete'] is False
    now[0] += 0.333
    trace.finish(export)
    report = log.report({}, {})
    payload = json.loads(report.split(JSON_MARKER)[1])
    top = payload['performance_summary']['slowest_10']
    assert len(top) == 10
    assert top[0]['operation'] == 'export' and top[0]['duration_ms'] == 333
    assert top[0]['over_100_ms'] is True
    assert [r['duration_ms'] for r in top] == sorted(
        [r['duration_ms'] for r in top], reverse=True
    )
    assert 'LANGSAM | export: 333.0 ms' in report
    assert 'physischen Anzeige' in report
