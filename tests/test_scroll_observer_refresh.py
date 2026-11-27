from types import SimpleNamespace
from nte_gear_optimizer_app import scroll_observer as module


def test_active_rate_is_refreshed_between_gestures_without_idle_native_reads(
    monkeypatch,
):
    calls = []
    monkeypatch.setattr(
        module,
        'display_refresh',
        lambda platform: {'active_hz': 60, 'native_max_hz': 120},
    )
    monkeypatch.setattr(
        module, 'active_display_refresh', lambda platform: calls.append(platform) or 120
    )
    window = SimpleNamespace(width=100, height=100, bind=lambda **kw: None)
    clock = SimpleNamespace(
        schedule_interval=lambda *a: SimpleNamespace(cancel=lambda: None)
    )
    observer = module.ScrollObserver(window, clock, 'android', lambda *a, **k: None)
    observer.tick()
    assert calls == []
    observer.motion(None, 'begin', SimpleNamespace(uid=1, sx=0, sy=0))
    assert calls == ['android'] and observer.metrics.refresh_hz == 120
    assert observer.display['active_hz'] == 120
