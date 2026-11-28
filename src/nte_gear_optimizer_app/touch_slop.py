"""Cached Android ViewConfiguration policy, shared by scrolls and buttons."""

from functools import lru_cache
from kivy.core.window import Window
from kivy.metrics import dp, Metrics
from kivy.utils import platform
from .touch_intent import TouchIntent


@lru_cache(maxsize=1)
def touch_slop_policy():
    result = {
        'window_px': float(dp(8)),
        'source': 'desktop fallback 8dp',
        'density': float(Metrics.density),
        'native_px': None,
        'window_per_native_px': 1.0,
    }
    if platform == 'android':
        try:
            from jnius import autoclass

            context = autoclass('org.kivy.android.PythonActivity').mActivity
            native = float(
                autoclass('android.view.ViewConfiguration')
                .get(context)
                .getScaledTouchSlop()
            )
            width = int(context.getWindow().getDecorView().getWidth())
            if native <= 0 or width <= 0:
                raise ValueError('Native touch geometry not available')
            ratio = Window.width / width
            result.update(
                window_px=native * ratio,
                native_px=native,
                window_per_native_px=ratio,
                source='Android ViewConfiguration.getScaledTouchSlop',
            )
        except Exception as error:
            result.update(
                source='UNVERIFIED_ANDROID_FALLBACK_8DP', reason=type(error).__name__
            )
    return result


class TouchIntentObserver:
    """One in-memory update per event and one queued journal entry per release."""

    def __init__(self, window, emit):
        self.window, self.emit = window, emit
        self.active = {}
        self.recent = []
        self.policy = touch_slop_policy()
        emit('touch_slop_policy', **self.policy)
        window.bind(on_motion=self.motion)

    def motion(self, _, kind, touch):
        if not getattr(touch, 'is_touch', True):
            return False
        # Native uid is stable for the lifetime of a touch. Format its report
        # identity once on begin, never allocate a label on every move.
        uid = touch.uid
        x, y = touch.sx * self.window.width, touch.sy * self.window.height
        if kind == 'begin':
            self.active[uid] = (str(uid), TouchIntent(x, y, self.policy['window_px']))
        else:
            current = self.active.get(uid)
            if current is not None:
                key, intent = current
                if kind == 'end':
                    row = dict(touch_id=key, **intent.finish(x, y))
                    self.recent.append(row)
                    self.recent = self.recent[-16:]
                    self.emit('touch_intent', **row)
                    del self.active[uid]
                else:
                    intent.move(x, y)
        return False

    def stop(self):
        self.window.unbind(on_motion=self.motion)
        self.active.clear()
