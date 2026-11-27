from types import SimpleNamespace

import pytest

from nte_gear_optimizer_app.keyboard_viewport import KeyboardViewport, scroll_padding


@pytest.mark.parametrize(
    'visible,height,surface,window,expected',
    [
        (False, 809, 1794, 1794, 0),
        (True, 809, 1794, 1794, 809),
        (True, 809, 1794, 897, 404.5),
        (True, 5000, 1794, 1794, 1794),
        (True, 0, 1794, 1794, 0),
    ],
)
def test_native_pixels_to_bounded_scroll_space(
    visible, height, surface, window, expected
):
    assert scroll_padding(visible, height, surface, window) == expected


@pytest.mark.parametrize(
    'values', [(True, -1, 100, 100), (True, 5, 0, 100), (True, float('nan'), 100, 100)]
)
def test_bad_viewport_is_not_used(values):
    with pytest.raises(ValueError):
        scroll_padding(*values)


def test_padding_tracks_ime_and_preserves_values_and_cancels():
    events = []
    cancelled = []
    app = SimpleNamespace(
        body=SimpleNamespace(padding=[0, 0, 0, 0]), inputs={'field': 'unchanged'}
    )
    window = SimpleNamespace(height=1794)
    state = [True, 809, 1794]
    clock = SimpleNamespace(
        schedule_interval=lambda callback, interval: SimpleNamespace(
            cancel=lambda: cancelled.append(True)
        )
    )
    viewport = KeyboardViewport(
        app, window, clock, lambda: state, lambda *a, **k: events.append((a, k))
    )
    viewport.update(0)
    assert app.body.padding == [0, 0, 0, 809]
    assert app.inputs == {'field': 'unchanged'}
    viewport.update(0)
    assert len(events) == 1
    state[0] = False
    viewport.update(0)
    assert app.body.padding == [0, 0, 0, 0]
    viewport.stop()
    assert cancelled == [True]


def test_native_read_failure_is_reported_without_blocking_app():
    events = []
    app = SimpleNamespace(body=SimpleNamespace(padding=[0, 0, 0, 0]))
    clock = SimpleNamespace(schedule_interval=lambda *a: None)

    def fail():
        raise RuntimeError('native unavailable')

    viewport = KeyboardViewport(
        app,
        SimpleNamespace(height=100),
        clock,
        fail,
        lambda *a, **k: events.append((a, k)),
    )
    viewport.update(0)
    viewport.update(0)
    assert len(events) == 1
    assert events[0][0] == ('keyboard_viewport_unavailable',)
    assert app.body.padding == [0, 0, 0, 0]
