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


def test_mode_switch_never_uses_stale60hz_to_claim_no_missed120hz_frames():
    now = [0.0]
    rows = []
    m = ScrollMetrics(lambda event, **row: rows.append(row), 60, lambda: now[0])
    m.begin('finger', 0, 0)
    now[0] = 0.01
    m.move('finger', 0, 2)
    m.changed('page', 1)
    m.frame()
    now[0] = 0.02
    m.set_refresh(120)
    m.changed('page', 2)
    m.frame()
    m.finish()
    assert rows[0]['status'] == 'UNVERIFIED_REFRESH_CHANGED'
    assert rows[0]['refresh_hz'] == 60 and rows[0]['refresh_hz_at_end'] == 120
    assert rows[0]['missed_frames_percent'] is None
    assert 'expected_refresh_slots' not in rows[0]
    # The next stable gesture uses the newly read120Hz reference.
    m.begin('next', 0, 0)
    now[0] = 0.03
    m.move('next', 0, 2)
    m.changed('page', 1)
    m.frame()
    now[0] += 1 / 120
    m.changed('page', 2)
    m.frame()
    m.finish()
    assert rows[-1]['refresh_hz'] == 120
    assert rows[-1]['missed_frames_percent'] == 0
