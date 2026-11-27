from nte_gear_optimizer_app.scroll_metrics import ScrollMetrics, frame_statistics
import pytest


@pytest.mark.parametrize('hz', [60, 120, 144])
def test_regular_and_dropped_frames(hz):
    frames = [i / hz for i in range(121)]
    result = frame_statistics(frames, hz)
    assert result['fps'] == pytest.approx(hz, abs=0.001)
    assert result['missed_frames_percent'] == 0
    dropped = frame_statistics([f for i, f in enumerate(frames) if i % 10 != 5], hz)
    assert dropped['missed_frames_percent'] > 8
    assert dropped['frame_interval_p95_ms'] > result['frame_interval_p95_ms']


def test_unknown_refresh_is_not_assumed_60():
    assert frame_statistics([0, 0.02, 0.04], None)['missed_frames_percent'] is None
    assert frame_statistics([], 120)['status'] == 'UNVERIFIED_INSUFFICIENT_FRAMES'


def test_actual_motion_gl_flip_and_settle():
    now = [0.0]
    rows = []
    m = ScrollMetrics(
        lambda event, **row: rows.append((event, row)), 120, lambda: now[0]
    )
    m.begin('finger', 0, 0)
    now[0] = 0.01
    m.move('finger', 0, 1)
    now[0] = 0.02
    m.changed('step1', 10)
    m.frame()
    now[0] = 0.03
    m.changed('step1', 20)
    m.frame()
    m.end('finger')
    now[0] = 0.2
    m.settle()
    assert len(rows) == 1
    row = rows[0][1]
    assert row['drawn_frames'] == 2 and row['first_drag_to_visible_movement_ms'] == 10
    assert row['distance_px'] == 10 and m.summary()['measured_gesture_count'] == 1
    # No logging per move or per frame; only one summary at gesture end.
    assert rows[0][0] == 'scroll_gesture_metrics'


def test_tap_programmatic_scroll_and_unrelated_touch_do_not_create_gesture():
    rows = []
    m = ScrollMetrics(lambda *a, **k: rows.append(k), 60)
    m.begin('a', 0, 0)
    m.move('b', 0, 30)
    m.changed('step1', 30)
    m.frame()
    m.end('a')
    m.finish()
    assert not rows
