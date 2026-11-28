"""A0 observational Kivy bridge; does not alter the 2A-3 input path."""

import weakref
import math
import time
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


def active_display_refresh(platform):
    # Called only after a display/window notification outside active gestures.
    if platform == 'android':
        from jnius import autoclass

        activity = autoclass('org.kivy.android.PythonActivity').mActivity
        return float(activity.getWindowManager().getDefaultDisplay().getRefreshRate())
    return display_refresh(platform)['active_hz']


class ScrollObserver:
    def __init__(self, window, clock, platform, emit, touch_slop=8):
        self.window, self.clock = window, clock
        self.platform = platform
        self.native_touch_uid = None
        self.touch_identifier = None
        self.pending_refresh = False
        self.refresh_reads = 1
        self.refresh_reads_during_gesture = 0
        self.subscription = None
        self.listener_status = 'NOT_ANDROID'
        self.touch_slop = touch_slop
        self.last_refresh_read = time.perf_counter()
        self.last_refresh_read_ms = None
        try:
            self.display = display_refresh(platform)
        except Exception as error:
            self.display = {
                'active_hz': None,
                'source': 'UNVERIFIED_READ_FAILED',
                'reason': type(error).__name__,
            }
        self.metrics = ScrollMetrics(
            emit, self.display['active_hz'], touch_slop=touch_slop
        )
        self.bound = weakref.WeakSet()
        self.labels = weakref.WeakKeyDictionary()
        window.bind(on_motion=self.motion, on_flip=self.metrics.frame)
        self.event = clock.schedule_interval(self.tick, 0.05)
        window.bind(size=self.queue_refresh)
        if platform == 'android':
            try:
                from .display_events import subscribe

                self.subscription = subscribe(self.native_notification)
                self.listener_status = 'REGISTERED'
            except Exception as error:
                self.listener_status = 'UNVERIFIED_' + type(error).__name__

    def native_notification(self, reason):
        # Android callback thread: schedule only. Never call JNI display getters.
        self.clock.schedule_once(lambda dt: self.queue_refresh(reason), 0)

    def queue_refresh(self, *args):
        self.pending_refresh = True
        if self.metrics.current is not None:
            self.metrics.invalidate_refresh('DISPLAY_OR_WINDOW_CHANGE_DEFERRED')

    def refresh_active_rate(self):
        if self.metrics.current is not None:
            self.pending_refresh = True
            return
        self.pending_refresh = False
        self.refresh_reads += 1
        started = time.perf_counter()
        try:
            hz = active_display_refresh(self.platform)
            if hz is not None and (not math.isfinite(hz) or hz <= 1):
                hz = None
            self.display['active_hz'] = hz
            self.display['active_rate_status'] = (
                'READ' if hz is not None else 'UNVERIFIED'
            )
        except Exception as error:
            hz = None
            self.display['active_hz'] = None
            self.display['active_rate_status'] = 'UNVERIFIED_READ_FAILED'
            self.display['active_rate_reason'] = type(error).__name__
        self.metrics.set_refresh(hz)
        self.last_refresh_read = time.perf_counter()
        self.last_refresh_read_ms = round((self.last_refresh_read - started) * 1000, 3)

    def tick(self, dt=0):
        self.metrics.settle(dt)
        if getattr(self, 'gc_policy', None) is not None:
            self.gc_policy.idle()
        if self.metrics.profile is not None and self.metrics.current is None:
            self.metrics.profile.idle_inventory()
        if self.pending_refresh and self.metrics.current is None:
            self.refresh_active_rate()

    def motion(self, _, kind, touch):
        if not getattr(touch, 'is_touch', True):
            return False
        x = touch.sx * self.window.width
        y = touch.sy * self.window.height
        if kind == 'begin':
            self.native_touch_uid = touch.uid
            self.touch_identifier = str(touch.uid)
            self.metrics.finish()
            self.metrics.begin(self.touch_identifier, x, y)
        elif touch.uid == self.native_touch_uid:
            if kind == 'update':
                self.metrics.move(self.touch_identifier, x, y)
            elif kind == 'end':
                self.metrics.end(self.touch_identifier)
                self.native_touch_uid = self.touch_identifier = None
        return False

    def attach(self, scroll, label):
        self.labels[scroll] = label
        if scroll in self.bound:
            return
        self.bound.add(scroll)

        def changed(w, y):
            overflow = max(0, w.viewport_size[1] - w.height)
            self.metrics.changed(self.labels[w], float(y) * overflow)

        scroll.bind(scroll_y=changed)

    def summary(self):
        physics = []
        for scroll, label in list(self.labels.items()):
            effect = getattr(scroll, 'effect_y', None)
            physics.append(
                {
                    'scroll': label,
                    'effect': type(effect).__name__,
                    'android_over_scroller': getattr(effect, 'native', None)
                    is not None,
                    'native_failure': getattr(effect, 'native_failure', None),
                    'scroll_distance': scroll.scroll_distance,
                    'scroll_timeout': scroll.scroll_timeout,
                }
            )
        return {
            'display': self.display,
            'physics': physics,
            'active_refresh_read_ms': self.last_refresh_read_ms,
            'active_refresh_sampling': 'Startup; display-listener/window-change notifications; deferred until gesture/inertia ends. No polling or getters during gestures.',
            'display_listener_status': self.listener_status,
            'refresh_reads': self.refresh_reads,
            'refresh_reads_during_gesture': self.refresh_reads_during_gesture,
            'refresh_pending': self.pending_refresh,
            **self.metrics.summary(),
        }

    def stop(self):
        self.metrics.finish()
        self.event.cancel()
        self.window.unbind(
            on_motion=self.motion, on_flip=self.metrics.frame, size=self.queue_refresh
        )
        if self.subscription is not None:
            from .display_events import unsubscribe

            unsubscribe(self.subscription)
            self.subscription = None
