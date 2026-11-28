"""Minimal native-screen correction, independent of the debug overlay."""

import math


from .frame_profile import phase


def required_lift(
    field_bottom, ime_top, gap, logical_scale, overflow, scroll_y, padding
):
    values = (field_bottom, ime_top, gap, logical_scale, overflow, scroll_y, padding)
    if not all(isinstance(v, (float, int)) and math.isfinite(v) for v in values):
        raise ValueError('Invalid viewport geometry')
    if logical_scale <= 0 or overflow < 0 or padding < 0 or not 0 <= scroll_y <= 1:
        raise ValueError('Invalid viewport bounds')
    lift = max(0.0, (field_bottom - (ime_top - gap)) * logical_scale)
    available = scroll_y * overflow
    return {
        'lift': lift,
        'padding_add': max(0.0, lift - available),
        'scroll_y': max(0.0, scroll_y - lift / overflow) if overflow else scroll_y,
    }


def minimum_bottom_padding(
    lowest_bottom, ime_top, gap, scale, overflow, scroll_y, padding, maximum
):
    required_lift(lowest_bottom, ime_top, gap, scale, overflow, scroll_y, padding)
    if not math.isfinite(maximum) or maximum < 0:
        raise ValueError('Invalid IME height')
    # Include remaining ordinary scroll range and existing padding. Only the
    # unreachable bottom of the lowest actual input needs additional range.
    extra = (lowest_bottom - (ime_top - gap)) * scale - scroll_y * overflow
    return max(0.0, min(maximum, padding + extra))


class MinimalKeyboardViewport:
    def __init__(self, app, window, clock, read_native, emit, gap=8):
        self.app, self.window, self.read_native, self.emit = (
            app,
            window,
            read_native,
            emit,
        )
        self.gap = gap
        self.target = None
        self.manual_target = None
        self.adjusted = False
        self.failed = False
        self.padded = []
        self.last_measurement = None
        self.native_reads = 0
        self.native_reads_while_touch = 0
        self.deferred_native_reads = 0
        self.event = clock.schedule_interval(self.update, 0.1)

    def reset(self):
        for body in self.padded:
            body.padding = [0, 0, 0, 0]
        self.padded.clear()
        self.target = None
        self.manual_target = None
        self.adjusted = False
        self.last_measurement = None

    def user_move(self):
        # A user must be able to scroll away from the old focused field to
        # reach the next one while the shared IME remains open. Do not let
        # the automatic correction pull the old field back after release.
        if self.target is not None:
            self.manual_target = self.target

    def field_bottom(self, widget, state):
        x, y = widget.to_window(*widget.pos)
        _, y, _ = self.window.render_context['modelview_mat'].transform_point(x, y, 0)
        left, top, width, height = state['surface_rect']
        return top + (self.window.height - y) * height / self.window.height

    def body_fields(self):
        fields = []
        for w in self.app.inputs.values():
            node, seen = w, set()
            while node is not None and id(node) not in seen:
                if getattr(node, 'opacity', 1) <= 0 or getattr(node, 'disabled', False):
                    break
                if node is self.app.body:
                    fields.append(w)
                    break
                seen.add(id(node))
                node = getattr(node, 'parent', None)
        return fields

    def focused(self):
        return next((w for w in self.body_fields() if getattr(w, 'focus', False)), None)

    @phase('viewport')
    def update(self, dt=0):
        try:
            widget = self.focused()
            if widget is None:
                self.reset()
                return
            # Correction already waits for touch-up. Avoid the JNI traversal
            # on the path that cannot adjust anything while the finger is down.
            if getattr(self.app, 'active_touches', None):
                self.deferred_native_reads += 1
                return
            self.native_reads += 1
            self.native_reads_while_touch += int(
                bool(getattr(self.app, 'active_touches', None))
            )
            state = self.read_native()
            if not state['visible']:
                self.reset()
                return
            if getattr(self.app, 'active_touches', None):
                return
            if self.target is not widget:
                self.target = widget
                self.manual_target = None
                self.adjusted = False
            _, _, _, surface_height = state['surface_rect']
            scale = self.window.height / surface_height
            gap = self.gap / scale
            overflow = max(0.0, self.app.body.height - self.app.scroll.height)
            padding = float(self.app.body.padding[3])
            lowest = max(self.field_bottom(w, state) for w in self.body_fields())
            needed = minimum_bottom_padding(
                lowest,
                state['visible_bottom'],
                gap,
                scale,
                overflow,
                self.app.scroll.scroll_y,
                padding,
                state['native_height'] * scale,
            )
            if abs(needed - padding) > 1:
                self.app.body.padding = [0, 0, 0, needed]
                if self.app.body not in self.padded:
                    self.padded.append(self.app.body)
                self.emit(
                    'keyboard_scroll_padding',
                    height=needed,
                    policy='minimal_unreachable_input_range',
                )
                return  # let the actual BoxLayout apply its changed minimum height
            if widget is self.manual_target:
                return  # never pull the old focused field back after a user swipe
            bottom = self.field_bottom(widget, state)
            result = required_lift(
                bottom,
                state['visible_bottom'],
                gap,
                scale,
                overflow,
                self.app.scroll.scroll_y,
                padding,
            )
            if result['lift'] > 1 and overflow > 0:
                self.app.scroll.scroll_y = result['scroll_y']
                self.adjusted = True
            elif self.adjusted and overflow > 0:
                excess = (state['visible_bottom'] - gap - bottom) * scale
                if excess > self.gap:
                    self.app.scroll.scroll_y = min(
                        1.0, self.app.scroll.scroll_y + excess / overflow
                    )
            measurement = (
                id(widget),
                round(bottom),
                round(state['visible_bottom']),
                round(padding),
            )
            if measurement != self.last_measurement:
                self.last_measurement = measurement
                self.emit(
                    'keyboard_field_geometry',
                    field=next(
                        (
                            ':'.join(k)
                            for k, w in self.app.inputs.items()
                            if w is widget
                        ),
                        None,
                    ),
                    field_bottom_px=round(bottom, 2),
                    ime_top_px=state['visible_bottom'],
                    gap_px=round(state['visible_bottom'] - bottom, 2),
                    padding_logical=padding,
                )
            self.failed = False
        except Exception as error:
            if not self.failed:
                from .debug_journal import private_traceback

                self.emit(
                    'keyboard_viewport_unavailable', stacktrace=private_traceback(error)
                )
                self.failed = True

    def stop(self):
        self.reset()
        self.event.cancel()


def android_geometry_reader():
    from jnius import autoclass, cast

    activity = autoclass('org.kivy.android.PythonActivity').mActivity
    version = autoclass('android.os.Build$VERSION').SDK_INT
    java_class = autoclass('java.lang.Class')
    surface_type = java_class.forName('android.view.SurfaceView')
    group_type = java_class.forName('android.view.ViewGroup')
    baseline = [None]

    def find(view):
        if surface_type.isInstance(view):
            return view
        if group_type.isInstance(view):
            group = cast('android.view.ViewGroup', view)
            for i in range(group.getChildCount()):
                result = find(group.getChildAt(i))
                if result is not None:
                    return result
        return None

    def read():
        decor = activity.getWindow().getDecorView()
        rect = autoclass('android.graphics.Rect')()
        decor.getWindowVisibleDisplayFrame(rect)
        if version >= 30:
            insets = decor.getRootWindowInsets()
            if insets is None:
                return {'visible': False}
            kind = autoclass('android.view.WindowInsets$Type').ime()
            visible = bool(insets.isVisible(kind))
            native_height = float(insets.getInsets(kind).bottom)
        else:
            baseline[0] = max(baseline[0] or rect.bottom, rect.bottom)
            native_height = max(0, baseline[0] - rect.bottom)
            visible = native_height > 0
        if not visible:
            return {'visible': False}
        surface = find(decor)
        if surface is None:
            raise RuntimeError('Native SurfaceView unavailable')
        location = [0, 0]
        surface.getLocationOnScreen(location)
        return {
            'visible': True,
            'native_height': native_height,
            'visible_bottom': float(rect.bottom),
            'surface_rect': [*location, surface.getWidth(), surface.getHeight()],
        }

    return read
