"""One explicitly owned native keyboard per Android input session.

Uses Kivy's public managed-mode/keyboard API. Widgets never own or release the
shared keyboard; it is detached before release. No global Window monkeypatch.
"""


class KeyboardSession:
    def __init__(self, window, clock, emit, configure_widget=None):
        self.window = window
        self.clock = clock
        self.emit = emit
        self.configure_widget = configure_widget
        self.keyboard = None
        self.active = None
        self.input_type = None
        self.close_event = None
        self.closing = False

    def _detach(self, widget):
        # Clear our active owner before focus=False triggers a bound callback.
        if self.active is widget:
            self.active = None
        widget.hide_keyboard()
        widget.focus = False
        widget.keyboard = None

    def focus_changed(self, widget, focused):
        if self.closing:
            return
        if focused:
            if self.close_event is not None:
                self.close_event.cancel()
                self.close_event = None
            if self.active is widget:
                return
            if self.active is not None:
                self._detach(self.active)
            if self.keyboard is not None and self.input_type != widget.input_type:
                self.close()
            new_keyboard = self.keyboard is None
            if new_keyboard:
                self.keyboard = self.window.request_keyboard(
                    self.native_closed,
                    widget,
                    input_type=widget.input_type,
                    keyboard_suggestions=widget.keyboard_suggestions,
                )
                self.input_type = widget.input_type
                self.emit('keyboard_session_open', input_type=self.input_type)
            if self.keyboard is None:
                widget.focus = False
                return
            # No old widget is still assigned when setting this property.
            self.active = widget
            self.keyboard.target = widget
            widget.keyboard = self.keyboard
            widget.show_keyboard()
            if self.configure_widget is not None:
                self.configure_widget(widget, new_keyboard)
            self.emit('keyboard_focus_handoff', input_type=self.input_type)
        elif self.active is widget:
            self._detach(widget)
            self.close_event = self.clock.schedule_once(self.close_if_idle, 0)

    def close_if_idle(self, dt):
        self.close_event = None
        if self.active is None:
            self.close()

    def native_closed(self):
        # Called by Window when Android Back/Done releases the keyboard.
        # Widgets use an explicitly assigned keyboard, so hide only unbinds.
        self.closing = True
        try:
            if self.active is not None:
                self._detach(self.active)
            self.keyboard = None
            self.input_type = None
            self.emit('keyboard_session_native_closed')
        finally:
            self.closing = False

    def close(self):
        if self.close_event is not None:
            self.close_event.cancel()
            self.close_event = None
        self.closing = True
        try:
            if self.active is not None:
                self._detach(self.active)
            keyboard = self.keyboard
            self.keyboard = None
            self.input_type = None
            if keyboard is not None:
                # All widget assignments have been removed before release.
                keyboard.release()
                self.emit('keyboard_session_closed')
        finally:
            self.closing = False
