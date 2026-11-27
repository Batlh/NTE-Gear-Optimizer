"""Observational input routing trace; never changes event results or focus."""

import time
import weakref
from collections import deque


class InputTrace:
    def __init__(self, app, sink):
        self.app = app
        self.sink = sink
        self.sequence = 0
        self.started = time.monotonic_ns()
        self.events = deque(maxlen=2000)
        self.attached = weakref.WeakSet()

    def emit(self, event, **data):
        self.sequence += 1
        row = {
            'seq': self.sequence,
            'ms': (time.monotonic_ns() - self.started) // 1000000,
            'event': event,
            **data,
        }
        self.events.append(row)
        try:
            self.sink(row)
        except Exception:
            # A diagnostic must not suppress or alter a user's input.
            pass

    def describe(self, widget):
        try:
            return self._describe(widget)
        except Exception as error:
            return {
                'class': type(widget).__name__,
                'diagnostic_error': type(error).__name__,
            }

    def _describe(self, widget):
        field = next(
            (
                ':'.join(key)
                for key, value in self.app.inputs.items()
                if value is widget
            ),
            None,
        )
        ancestors = []
        node = widget
        while node is not None and node not in ancestors:
            ancestors.append(node)
            node = getattr(node, 'parent', None)
        return {
            'class': type(widget).__name__,
            'uid': widget.uid,
            'field': field,
            'in_white_subtree': getattr(self.app, 'white_box', None) in ancestors,
            'depth': len(ancestors),
            'label': str(getattr(widget, 'text', ''))[:120],
            'enabled': not widget.disabled,
            'tree_visible': (
                getattr(self.app, 'root_box', None) in ancestors
                or getattr(self.app, 'root_window', None) in ancestors
            )
            and all(
                getattr(w, 'opacity', 1) > 0
                and getattr(w, 'height', 1) > 0
                and getattr(w, 'width', 1) > 0
                for w in ancestors
            ),
            'rect': [*widget.to_window(*widget.pos), *widget.size],
        }

    def attach_tree(self, root):
        for widget in root.walk():
            if widget in self.attached:
                continue
            self.attached.add(widget)
            original = widget.on_touch_down

            def traced(touch, original=original, widget=widget):
                accepted = original(touch)
                if accepted:
                    self.emit(
                        'touch_accepted',
                        touch_id=str(touch.uid),
                        position=list(touch.pos),
                        device=str(getattr(touch, 'device', '')),
                        widget=self.describe(widget),
                    )
                return accepted

            widget.on_touch_down = traced
            if hasattr(widget, 'focus'):
                widget.bind(
                    focus=lambda w, value: self.emit(
                        'focus', widget=self.describe(w), focused=bool(value)
                    )
                )

    def attach_window(self, window):
        for name in ('request_keyboard', 'release_keyboard'):
            original = getattr(window, name)

            def traced(*args, original=original, name=name, **kwargs):
                targets = [
                    self.describe(a) for a in args if hasattr(a, 'on_touch_down')
                ]
                self.emit(name + '_before', targets=targets)
                result = original(*args, **kwargs)
                self.emit(name + '_after', targets=targets)
                return result

            setattr(window, name, traced)
        window.bind(
            keyboard_height=lambda _, value: self.emit('keyboard_height', value=value),
            size=lambda _, value: self.emit('window_size', value=list(value)),
        )

        def motion(_, kind, touch):
            if kind in ('begin', 'end'):
                self.emit(
                    'motion_' + kind,
                    touch_id=str(touch.uid),
                    device=str(getattr(touch, 'device', '')),
                    normalized=[touch.sx, touch.sy],
                )
            return False

        window.bind(on_motion=motion)
