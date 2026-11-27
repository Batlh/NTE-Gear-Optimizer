"""Keep the last scroll input reachable above Android's native IME.

SDL2 below_target pans the surface but does not resize the ScrollView.
Padding is layout space, never an invisible touch-consuming widget. The
controller is independent of DebugControl and never changes field values.
"""

import math


def scroll_padding(visible, native_height, surface_height, window_height):
    if not visible:
        return 0.0
    values = (native_height, surface_height, window_height)
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values):
        raise ValueError('Invalid keyboard viewport dimensions')
    if native_height < 0 or surface_height <= 0 or window_height <= 0:
        raise ValueError('Invalid keyboard viewport dimensions')
    return min(window_height, native_height * window_height / surface_height)


class KeyboardViewport:
    def __init__(self, app, window, clock, read_native, emit):
        self.app = app
        self.window = window
        self.read_native = read_native
        self.emit = emit
        self.last_padding = None
        self.failed = False
        self.event = clock.schedule_interval(self.update, 0.1)

    def update(self, dt):
        try:
            state = self.read_native()
            padding = scroll_padding(*state, self.window.height)
            if self.last_padding is None or abs(padding - self.last_padding) > 1:
                self.app.body.padding = [0, 0, 0, padding]
                self.last_padding = padding
                self.emit('keyboard_scroll_padding', height=padding)
            self.failed = False
        except Exception as error:
            if not self.failed:
                self.emit('keyboard_viewport_unavailable', reason=type(error).__name__)
                self.failed = True

    def stop(self):
        self.event.cancel()


def android_keyboard_reader():
    from jnius import autoclass

    activity = autoclass('org.kivy.android.PythonActivity').mActivity
    version = autoclass('android.os.Build$VERSION').SDK_INT
    baseline_bottom = [None]

    def read():
        decor = activity.getWindow().getDecorView()
        if version >= 30:
            insets = decor.getRootWindowInsets()
            if insets is None:
                return False, 0, max(1, decor.getHeight())
            kind = autoclass('android.view.WindowInsets$Type').ime()
            return (
                bool(insets.isVisible(kind)),
                insets.getInsets(kind).bottom,
                decor.getHeight(),
            )
        rect = autoclass('android.graphics.Rect')()
        decor.getWindowVisibleDisplayFrame(rect)
        baseline_bottom[0] = max(baseline_bottom[0] or rect.bottom, rect.bottom)
        height = max(0, baseline_bottom[0] - rect.bottom)
        return height > 0, height, decor.getHeight()

    return read
