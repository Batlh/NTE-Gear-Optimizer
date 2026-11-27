"""Fast gesture intent, non-focusing preview, native Android fling physics.

Kivy2.3.2 is pinned. The isolated touch tests guard the two protected
ScrollView dispatch hooks used to remove its delayed synthetic touch-up.
"""

from functools import partial
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.effects.scroll import ScrollEffect
from kivy.graphics import Color, InstructionGroup, Line
from kivy.metrics import dp
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.utils import platform


class NativeScrollEffect(ScrollEffect):
    def __init__(self, **kwargs):
        self.native = None
        self.native_failure = None
        self.fling_started = False
        super().__init__(**kwargs)
        self.drag_threshold = dp(1)
        self.friction = 0.015
        if platform == 'android':
            try:
                from jnius import autoclass

                context = autoclass('org.kivy.android.PythonActivity').mActivity
                self.native = autoclass('android.widget.OverScroller')(context)
                self.native.setFriction(
                    autoclass('android.view.ViewConfiguration').getScrollFriction()
                )
            except Exception as error:
                from .debug_journal import private_traceback

                self.native_failure = private_traceback(error)

    def start(self, val, t=None):
        if self.native is not None:
            self.native.forceFinished(True)
        self.fling_started = False
        return super().start(val, t)

    def cancel(self):
        if self.native is not None:
            self.native.forceFinished(True)
        self.fling_started = False
        self.is_manual = False
        self.velocity = 0
        self.trigger_velocity_update.cancel()

    def update_velocity(self, dt):
        if self.native is None:
            return super().update_velocity(dt)
        if self.is_manual:
            return
        if not self.fling_started:
            if abs(self.velocity) <= self.min_velocity:
                return
            lo, hi = sorted((round(self.min), round(self.max)))
            self.native.fling(
                0, round(self.value), 0, round(self.velocity), 0, 0, lo, hi
            )
            self.fling_started = True
        if self.native.computeScrollOffset():
            self.value = float(self.native.getCurrY())
            self.trigger_velocity_update()
        else:
            self.velocity = 0
            self.fling_started = False


class ResponsiveScrollView(ScrollView):
    def __init__(self, **kwargs):
        kwargs.setdefault('scroll_distance', dp(1))
        kwargs.setdefault('scroll_timeout', 55)
        kwargs.setdefault('effect_cls', NativeScrollEffect)
        super().__init__(**kwargs)
        self.preview = None

    def _change_touch_mode(self, *args):
        # Do not send an unconfirmed gesture to a child while the finger is
        # still down: a later swipe must not focus/open the keyboard.
        # Optical preview is independent; confirmed taps are delivered on up.
        return

    def simulate_touch_down(self, touch):
        result = super().simulate_touch_down(touch)
        Clock.schedule_once(partial(self._do_touch_up, touch), 0)
        return result

    def _do_touch_up(self, touch, *args):
        key = 'nte.released.' + str(self.uid)
        if touch.ud.get(key):
            return
        touch.ud[key] = True
        # Kivy's old scheduled+200ms call becomes an idempotent no-op.
        return super()._do_touch_up(touch, *args)

    def preview_target(self, touch):
        if self._viewport is None or not self.collide_point(*touch.pos):
            return None
        wx, wy = self.parent.to_window(*touch.pos)
        for widget in self._viewport.walk():
            if not isinstance(widget, (Button, TextInput)) or widget.disabled:
                continue
            x, y = widget.to_window(*widget.pos)
            if x <= wx <= x + widget.width and y <= wy <= y + widget.height:
                return widget
        return None

    def show_preview(self, touch):
        self.clear_preview()
        target = self.preview_target(touch)
        if target is None:
            return
        group = InstructionGroup()
        group.add(Color(0.65, 0.84, 0.42, 0.9))
        group.add(Line(rectangle=(*target.pos, *target.size), width=dp(1.5)))
        target.canvas.after.add(group)
        previous = target.state if isinstance(target, Button) else None
        if isinstance(target, Button):
            target.state = 'down'
        self.preview = (target, group, previous)
        app = App.get_running_app()
        if getattr(app, 'debug', None):
            app.debug.performance.feedback('pressed_preview', touch.uid)
            app.debug.journal.emit(
                'touch_feedback_preview',
                touch_id=str(touch.uid),
                widget=app.debug.trace.describe(target),
            )

    def clear_preview(self):
        if self.preview is None:
            return
        target, group, previous = self.preview
        self.preview = None
        target.canvas.after.remove(group)
        if previous is not None:
            target.state = previous

    def on_touch_down(self, touch):
        if not self.disabled:
            self.show_preview(touch)
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        result = super().on_touch_move(touch)
        intent = touch.ud.get(self._get_uid(), {})
        if intent.get('mode') == 'scroll':
            self.clear_preview()
        return result

    def on_touch_up(self, touch):
        self.clear_preview()
        return super().on_touch_up(touch)
