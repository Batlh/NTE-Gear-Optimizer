"""Real OS mouse inputs on actual app controls. No synthetic widget dispatch."""

from kivy.metrics import dp
from kivy.clock import Clock
from nte_gear_optimizer_app.viewmodel import ComparisonViewModel
from nte_gear_optimizer_app.touch_slop import touch_slop_policy


def cases(app, native_button):
    policy = touch_slop_policy()
    app.evidence.append({'h01_touch_slop_policy': policy})

    def gesture(widget, drift, hold):
        yield from app.position_for_hold(widget)
        origin = widget.to_window(widget.center_x, widget.center_y)

        class Point:
            center_x, center_y = origin[0], origin[1] + dp(drift)

            def to_window(self, x, y):
                return x, y

        native_button(widget, True)
        yield hold / 2
        assert widget.state == 'down' if hasattr(widget, 'state') else True
        native_button(Point(), None)
        yield hold / 2
        native_button(Point(), False)
        yield 0.7

    # Footer controls too: a >slop move still inside the button must cancel.
    yield from gesture(app.next_button, 16, 0.4)
    assert app.vm.step == 0, 'Swipe on Weiter triggered navigation'
    for drift, hold in [(3, 0.3), (6, 0.4)]:
        yield from gesture(app.next_button, drift, hold)
        assert app.vm.step == 1, ('Held Weiter lost', drift, hold)
        app.click(app.back_button)
        yield from app.wait_click(lambda: app.vm.step == 0, 'h01_return')
        selector = app.selector_widgets['Charakter']
        app.scroll.scroll_to(selector, padding=30, animate=False)
        yield 0.2
        yield from gesture(selector, drift, hold)
        assert app.active_selector is not None, ('Held selector lost', drift)
        app.active_selector[1].dismiss(animation=False)
        app.active_selector = None
        yield 0.2
        yield from gesture(app.debug_button, drift, hold)
        assert app.active_debug is not None, ('Held Debug lost', drift)
        app.active_debug[0].dismiss(animation=False)
        app.active_debug = None
        field = app.inputs[('level', 'ArkLevel')]
        app.scroll.scroll_to(field, padding=30, animate=False)
        yield 0.2
        yield from gesture(field, drift, hold)
        assert field.focus, ('Held field did not focus', drift)
        field.focus = False
        app.evidence.append(
            {'h01_native_tap_set': 'PASS', 'drift_dp': drift, 'hold_seconds': hold}
        )
    # A real swipe on a scrollable selector must scroll, not select/open.
    app.scroll.scroll_y = 1
    yield 0.3
    selector = app.selector_widgets['Charakter']
    before = app.scroll.scroll_y
    yield from gesture(selector, 32, 0.4)
    assert app.active_selector is None, 'Swipe opened selector'
    assert abs(app.scroll.scroll_y - before) > 0.001, 'Swipe did not scroll'
    app.scroll.scroll_to(app.inputs[('level', 'ArkLevel')], animate=False)
    yield 0.3
    field = app.inputs[('level', 'ArkLevel')]
    yield from gesture(field, 16, 0.4)
    assert not field.focus, 'Swipe focused field'
    app.vm = ComparisonViewModel()
    app.vm.set_override('ProfileType', 'DAMAGE')
    app.vm.set_override('ScalingStat', 'ANG')
    app.vm.step = 1
    app.render()
    yield 0.4
    for drift, hold in [(3, 0.3), (6, 0.4)]:
        zero = app.zero_buttons[0]
        app.scroll.scroll_to(zero, animate=False)
        yield 0.3
        boundary = app.debug.journal.seq
        yield from gesture(zero, drift, hold)
        assert any(
            e['seq'] > boundary and e['event'] == 'zero_bonus'
            for e in app.debug.journal.events()
        ), 'Held zero action lost'
    recent = [e for e in app.debug.journal.events() if e['event'] == 'touch_intent']
    assert any(e['classification'] == 'SWIPE' for e in recent)
    assert any(e['classification'] == 'TAP' and e['duration_ms'] >= 300 for e in recent)
    app.evidence.append(
        {'h01_touch_intent_journal': 'PASS', 'recent_intents': recent[-20:]}
    )
    app.vm = ComparisonViewModel()
    app.render()
    yield 0.2
