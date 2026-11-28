from types import SimpleNamespace
from nte_gear_optimizer_app import scroll_observer as module


def make(monkeypatch):
    reads = []
    bindings = {}
    monkeypatch.setattr(
        module, 'display_refresh', lambda p: {'active_hz': 120, 'native_max_hz': 120}
    )
    monkeypatch.setattr(
        module, 'active_display_refresh', lambda p: reads.append('read') or 60
    )
    window = SimpleNamespace(
        width=100,
        height=100,
        bind=lambda **kw: bindings.update(kw),
        unbind=lambda **kw: None,
    )
    clock = SimpleNamespace(
        schedule_interval=lambda *a: SimpleNamespace(cancel=lambda: None),
        schedule_once=lambda fn, dt: fn(dt),
    )
    observer = module.ScrollObserver(
        window, clock, 'win', lambda *a, **kw: None, touch_slop=8
    )
    return observer, reads, bindings


def test_no_native_reads_on_touch_or_long_active_gesture(monkeypatch):
    o, reads, b = make(monkeypatch)
    o.motion(None, 'begin', SimpleNamespace(uid=1, sx=0, sy=0))
    for _ in range(100):
        o.tick()
    o.refresh_active_rate()  # even an accidental direct request is deferred
    assert reads == [] and o.refresh_reads == 1
    assert o.pending_refresh


def test_notification_during_gesture_is_invalidated_and_read_after_finish(monkeypatch):
    o, reads, b = make(monkeypatch)
    o.motion(None, 'begin', SimpleNamespace(uid=1, sx=0, sy=0))
    o.native_notification('display_changed')
    assert reads == [] and o.metrics.current['refresh_changed']
    o.metrics.finish()
    o.tick()
    assert reads == ['read'] and o.metrics.refresh_hz == 60
    assert o.refresh_reads_during_gesture == 0
    for _ in range(20):
        o.tick()
    assert reads == ['read']


def test_window_resize_refreshes_once_when_idle(monkeypatch):
    o, reads, b = make(monkeypatch)
    b['size'](None, (200, 100))
    o.tick()
    assert reads == ['read']


def test_slop_metric_ignores_initial_jitter_time():
    now = [0.0]
    rows = []
    m = module.ScrollMetrics(
        lambda event, **r: rows.append(r), 120, lambda: now[0], touch_slop=8
    )
    m.begin('1', 0, 0)
    now[0] = 0.01
    m.move('1', 0, 6)
    m.changed('page', 10)
    m.frame()
    assert not m.current['frames']
    now[0] = 0.1
    m.move('1', 0, 9)
    now[0] = 0.105
    m.changed('page', 11)
    m.frame()
    m.finish()
    assert rows[0]['first_drag_to_visible_movement_ms'] == 5
    assert rows[0]['first_motion_to_visible_movement_ms'] == 95
    assert rows[0]['first_movement_startpoint'] == 'SYSTEM_TOUCH_SLOP_CROSSED'
