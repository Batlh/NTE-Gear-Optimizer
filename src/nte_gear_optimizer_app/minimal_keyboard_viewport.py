"""Minimal native-screen correction, independent of the debug overlay."""

import math


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
        self.adjusted = False
        self.failed = False
        self.padded = []
        self.last_measurement = None
        self.event = clock.schedule_interval(self.update, 0.1)

    def reset(self):
        for body in self.padded:
            body.padding = [0, 0, 0, 0]
        self.padded.clear()
        self.target = None
        self.adjusted = False
        self.last_measurement = None

    def field_bottom(self, widget, state):
        x, y = widget.to_window(*widget.pos)
        _, y, _ = self.window.render_context['modelview_mat'].transform_point(x, y, 0)
        left, top, width, height = state['surface_rect']
        return top + (self.window.height - y) * height / self.window.height

    def focused(self):
        for w in self.app.inputs.values():
            if not getattr(w, 'focus', False):
                continue
            node = w
            seen = set()
            while node is not None and id(node) not in seen:
                if node is self.app.body:
                    return w
                seen.add(id(node))
                node = getattr(node, 'parent', None)
        return None

    def update(self, dt=0):
        try:
            widget = self.focused()
            if widget is None:
                self.reset()
                return
            state = self.read_native()
            if not state['visible']:
                self.reset()
                return
            if getattr(self.app, 'active_touches', None):
                return
            if self.target is not widget:
                self.target = widget
                self.adjusted = False
            _, _, _, surface_height = state['surface_rect']
            scale = self.window.height / surface_height
            bottom = self.field_bottom(widget, state)
            gap = self.gap / scale
            overflow = max(0.0, self.app.body.height - self.app.scroll.height)
            padding = float(self.app.body.padding[3])
            result = required_lift(
                bottom,
                state['visible_bottom'],
                gap,
                scale,
                overflow,
                self.app.scroll.scroll_y,
                padding,
            )
            if result['padding_add'] > 1:
                maximum = state['native_height'] * scale
                added = min(maximum - padding, result['padding_add'])
                if added > 1:
                    self.app.body.padding = [0, 0, 0, padding + added]
                    if self.app.body not in self.padded:
                        self.padded.append(self.app.body)
                    self.adjusted = True
                    self.emit(
                        'keyboard_scroll_padding',
                        height=padding + added,
                        policy='minimal_native_geometry',
                    )
                return
            if result['lift'] > 1 and overflow > 0:
                self.app.scroll.scroll_y = result['scroll_y']
                self.adjusted = True
            elif padding > 0:
                excess = max(0.0, (state['visible_bottom'] - gap - bottom) * scale)
                if excess > 1:
                    self.app.body.padding = [0, 0, 0, max(0.0, padding - excess)]
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
