"""New frame diagnostics must not evict the existing event/error evidence."""

from nte_gear_optimizer_app.debug_journal import DebugJournal
from nte_gear_optimizer_app.scroll_metrics import ScrollMetrics


class BufferedProfile:
    def begin(self):
        pass

    def finish(self):
        return {
            'rows': [[i, 8.33, 0, 0, 1, 0, 1, 2, 0, 0] for i in range(1200)],
            'rows_retained': 1200,
            'frames_observed': 1200,
        }


def test_frame_data_stays_in_report_state_without_displacing_early_exception(tmp_path):
    log = DebugJournal(tmp_path, buffered=True)
    try:
        raise ValueError('NTE_FRAME_RETENTION_TEST_EXCEPTION')
    except ValueError as error:
        log.exception(error, caught=True)
    log.emit('diagnostic_prefill', detail='x' * 300000)
    for i in range(250):
        log.emit('touch_fixture', index=i)
    now = [0.0]
    metrics = ScrollMetrics(log.emit, 60, clock=lambda: now[0], touch_slop=8)
    metrics.profile = BufferedProfile()
    for i in range(40):
        metrics.begin(str(i), 0, 0)
        now[0] += 0.1
        metrics.move(str(i), 9, 0)
        for pos in [10, 20, 30]:
            metrics.changed('page', pos)
            now[0] += 1 / 60
            metrics.frame()
        metrics.finish()
    events = log.events()
    assert any(
        'NTE_FRAME_RETENTION_TEST_EXCEPTION' in r.get('stacktrace', '') for r in events
    )
    emitted = [r for r in events if r['event'] == 'scroll_gesture_metrics']
    assert len(emitted) == 40
    assert all(
        'frame_profile' not in r and r['frame_profile_in_report_state'] for r in emitted
    )
    gestures = metrics.summary()['gestures']
    assert len(gestures) == 40
    assert all('rows' not in g['frame_profile'] for g in gestures[:-5])
    assert all(len(g['frame_profile']['rows']) == 1200 for g in gestures[-5:])
