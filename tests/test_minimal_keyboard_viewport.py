from types import SimpleNamespace
import pytest
from nte_gear_optimizer_app.minimal_keyboard_viewport import (
    required_lift,
    MinimalKeyboardViewport,
)


def test_padding_only_for_unavailable_scroll_distance():
    assert required_lift(1200, 1000, 20, 1, 400, 0.5, 0) == {
        'lift': 220,
        'padding_add': 20,
        'scroll_y': 0,
    }
    row = required_lift(1200, 1000, 20, 1, 1000, 0.5, 0)
    assert row['padding_add'] == 0 and row['scroll_y'] == pytest.approx(0.28)
    assert required_lift(900, 1000, 20, 1, 1000, 0.5, 0)['lift'] == 0


def test_minimal_padding_and_reset_without_changing_inputs():
    body = SimpleNamespace(height=300, padding=[0, 0, 0, 0], parent=None)
    widget = SimpleNamespace(
        focus=True, parent=body, pos=(0, 200), to_window=lambda *pos: pos
    )
    app = SimpleNamespace(
        body=body,
        scroll=SimpleNamespace(height=300, scroll_y=0),
        inputs={('y', 'ScaleDirect'): widget},
        active_touches=set(),
    )
    window = SimpleNamespace(
        height=500,
        render_context={'modelview_mat': SimpleNamespace(transform_point=lambda *p: p)},
    )
    state = {
        'visible': True,
        'native_height': 300,
        'visible_bottom': 200,
        'surface_rect': [0, 0, 100, 500],
    }
    cancelled = []
    clock = SimpleNamespace(
        schedule_interval=lambda *a: SimpleNamespace(
            cancel=lambda: cancelled.append(True)
        )
    )
    view = MinimalKeyboardViewport(
        app, window, clock, lambda: state, lambda *a, **k: None, gap=8
    )
    view.update()
    assert body.padding[3] == 108  # required, not the complete300px IME
    assert app.inputs[('y', 'ScaleDirect')] is widget
    state['visible'] = False
    view.update()
    assert body.padding == [0, 0, 0, 0]
    view.stop()
    assert cancelled == [True]


def test_geometry_failure_is_local_and_does_not_gate_calculation():
    events = []
    clock = SimpleNamespace(schedule_interval=lambda *a: None)

    def fail():
        raise RuntimeError('fixture native unavailable')

    view = MinimalKeyboardViewport(
        SimpleNamespace(),
        SimpleNamespace(),
        clock,
        fail,
        lambda *a, **k: events.append((a, k)),
    )
    view.update()
    view.update()
    assert len(events) == 1 and 'RuntimeError' in events[0][1]['stacktrace']
