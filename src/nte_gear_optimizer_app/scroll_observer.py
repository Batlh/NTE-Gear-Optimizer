"""A0 observational Kivy bridge; does not alter the 2A-3 input path."""

import weakref
from .scroll_metrics import ScrollMetrics


def display_refresh(platform):
    if platform == 'android':
        from jnius import autoclass

        activity = autoclass('org.kivy.android.PythonActivity').mActivity
        display = activity.getWindowManager().getDefaultDisplay()
        active = float(display.getRefreshRate())
        mode = display.getMode()
        supported = [
            float(m.getRefreshRate())
            for m in display.getSupportedModes()
            if m.getPhysicalWidth() == mode.getPhysicalWidth()
            and m.getPhysicalHeight() == mode.getPhysicalHeight()
        ]
        return {
            'active_hz': active,
            'native_max_hz': max(supported or [active]),
            'source': 'Android Display.getRefreshRate/getSupportedModes',
        }
    if platform == 'win':
        import ctypes
        from ctypes import wintypes

        user, gdi = ctypes.windll.user32, ctypes.windll.gdi32
        user.GetDC.argtypes = [wintypes.HWND]
        user.GetDC.restype = wintypes.HDC
        user.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
        gdi.GetDeviceCaps.argtypes = [wintypes.HDC, ctypes.c_int]
        hdc = user.GetDC(None)
        try:
            hz = int(gdi.GetDeviceCaps(hdc, 116))
        finally:
            user.ReleaseDC(None, hdc)
        return {
            'active_hz': hz if hz > 1 else None,
            'native_max_hz': None,
            'source': 'Win32 GetDeviceCaps VREFRESH; virtual-display values may be unknown',
        }
    return {
        'active_hz': None,
        'native_max_hz': None,
        'source': 'UNVERIFIED_PLATFORM_REFRESH',
    }


class ScrollObserver:
    def __init__(self, window, clock, platform, emit):
        self.window, self.clock = window, clock
        try:
            self.display = display_refresh(platform)
        except Exception as error:
            self.display = {
                'active_hz': None,
                'source': 'UNVERIFIED_READ_FAILED',
                'reason': type(error).__name__,
            }
        self.metrics = ScrollMetrics(emit, self.display['active_hz'])
        self.bound = weakref.WeakSet()
        window.bind(on_motion=self.motion, on_flip=self.metrics.frame)
        self.event = clock.schedule_interval(self.metrics.settle, 0.05)

    def motion(self, _, kind, touch):
        identifier = str(touch.uid)
        point = (touch.sx * self.window.width, touch.sy * self.window.height)
        if kind == 'begin':
            self.metrics.begin(identifier, *point)
        elif kind == 'update':
            self.metrics.move(identifier, *point)
        elif kind == 'end':
            self.metrics.end(identifier)
        return False

    def attach(self, scroll, label):
        if scroll in self.bound:
            return
        self.bound.add(scroll)

        def changed(w, y):
            overflow = max(0, w.viewport_size[1] - w.height)
            self.metrics.changed(label, float(y) * overflow)

        scroll.bind(scroll_y=changed)

    def summary(self):
        return {'display': self.display, **self.metrics.summary()}

    def stop(self):
        self.metrics.finish()
        self.event.cancel()
        self.window.unbind(on_motion=self.motion, on_flip=self.metrics.frame)
