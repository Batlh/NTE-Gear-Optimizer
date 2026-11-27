from types import SimpleNamespace

from nte_gear_optimizer_app.keyboard_session import KeyboardSession


class Event:
    def __init__(self, callback):
        self.callback = callback
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class Clock:
    def __init__(self):
        self.pending = []

    def schedule_once(self, callback, delay):
        event = Event(callback)
        self.pending.append(event)
        return event

    def flush(self):
        pending, self.pending = self.pending, []
        for event in pending:
            if not event.cancelled:
                event.callback(0)


class Window:
    def __init__(self):
        self.requests = 0
        self.releases = 0
        self.widgets = []

    def request_keyboard(self, callback, target, **kwargs):
        self.requests += 1

        def release():
            assert all(w.keyboard is None for w in self.widgets)
            self.releases += 1
            callback()

        self.native_close = callback
        return SimpleNamespace(target=target, release=release)


class Widget:
    input_type = 'text'
    keyboard_suggestions = True
    focus = False
    keyboard = None

    def __init__(self):
        self.binds = 0

    def show_keyboard(self):
        self.binds += 1

    def hide_keyboard(self):
        self.binds -= 1


def setup():
    window, clock = Window(), Clock()
    journal = []
    session = KeyboardSession(
        window, clock, lambda event, **data: journal.append((event, data))
    )
    a, b, c = Widget(), Widget(), Widget()
    window.widgets = [a, b, c]
    return session, window, clock, a, b, c, journal


def focus(session, widget):
    widget.focus = True
    session.focus_changed(widget, True)


def test_three_field_handoff_does_not_release_or_request_again():
    session, window, clock, a, b, c, journal = setup()
    for widget in [a, b, c, b, a, a]:
        focus(session, widget)
        clock.flush()
        assert session.active is widget
        assert widget.keyboard is session.keyboard
        assert session.keyboard.target is widget
        assert window.requests == 1 and window.releases == 0
    assert a.binds == 1 and b.binds == 0 and c.binds == 0


def test_done_detaches_before_native_release():
    session, window, clock, a, b, c, journal = setup()
    focus(session, a)
    a.focus = False
    session.focus_changed(a, False)
    assert a.keyboard is None and window.releases == 0
    clock.flush()
    assert window.releases == 1 and session.keyboard is None


def test_transient_focus_gap_is_cancelled_by_next_field():
    session, window, clock, a, b, c, journal = setup()
    focus(session, a)
    a.focus = False
    session.focus_changed(a, False)
    focus(session, b)
    clock.flush()
    assert window.requests == 1 and window.releases == 0 and session.active is b


def test_native_back_detaches_and_next_tap_requests_clean_keyboard():
    session, window, clock, a, b, c, journal = setup()
    focus(session, a)
    window.native_close()
    assert session.active is None and a.keyboard is None and not a.focus
    focus(session, b)
    assert window.requests == 2 and session.active is b


def test_navigation_closes_and_keyboard_type_can_change():
    session, window, clock, a, b, c, journal = setup()
    focus(session, a)
    b.input_type = 'number'
    focus(session, b)
    assert window.requests == 2 and window.releases == 1
    session.close()
    assert window.releases == 2
    assert all(widget.keyboard is None for widget in [a, b, c])
