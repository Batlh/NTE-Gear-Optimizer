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
from .touch_intent import TouchIntent
from .touch_slop import touch_slop_policy


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
        self.skip_tap_stop = False
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

    def discard_tap(self):
        # Kivy stops effects even in unknown/tap mode. Its stop(val) would
        # otherwise apply the last sub-slop displacement and start a fling.
        self.cancel()
        self.skip_tap_stop = True

    def stop(self, val, t=None):
        if getattr(self, 'skip_tap_stop', False):
            self.skip_tap_stop = False
            return
        return super().stop(val, t)

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
        kwargs.setdefault('scroll_distance', touch_slop_policy()['window_px'])
        kwargs.setdefault('scroll_timeout', 55)
        kwargs.setdefault('effect_cls', NativeScrollEffect)
        super().__init__(**kwargs)
        self.preview = None

    def _get_uid(self, prefix='sv'):
        # Pinned Kivy2.3.2 formats these keys on every touch dispatch. Their
        # value is immutable for a widget; preserve the exact base spelling.
        if prefix == 'sv':
            value = getattr(self, '_nte_sv_key', None)
            if value is None:
                value = self._nte_sv_key = super()._get_uid(prefix)
            return value
        if prefix == 'svavoid':
            value = getattr(self, '_nte_avoid_key', None)
            if value is None:
                value = self._nte_avoid_key = super()._get_uid(prefix)
            return value
        return super()._get_uid(prefix)

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

    def on_scroll_start(self, touch, check_children=True):
        result = super().on_scroll_start(touch, check_children)
        state = touch.ud.get(self._get_uid())
        if (
            state is not None
            and not touch.ud.get('in_bar_x')
            and not touch.ud.get('in_bar_y')
        ):
            state['nte_intent'] = TouchIntent(touch.x, touch.y, self.scroll_distance)
        return result

    def on_scroll_move(self, touch):
        state = touch.ud.get(self._get_uid())
        intent = state.get('nte_intent') if state is not None else None
        if intent is not None and state.get('mode') == 'unknown':
            # Kivy sums abs(dx/dy). Repeated sub-slop jitter must NOT add up
            # to a swipe; duration/timeout never changes this decision.
            if intent.move(touch.x, touch.y) == 'TAP':
                return True
            state['mode'] = 'scroll'
            self.clear_preview()
            # The effect still starts at the original down coordinate, so
            # crossing the slop applies the full finger displacement now.
        return super().on_scroll_move(touch)

    def on_scroll_stop(self, touch, check_children=True):
        state = touch.ud.get(self._get_uid())
        intent = state.get('nte_intent') if state is not None else None
        if intent is not None:
            if intent.move(touch.x, touch.y) == 'SWIPE':
                state['mode'] = 'scroll'
            elif state.get('mode') == 'unknown':
                for enabled, effect in [
                    (self.do_scroll_x, self.effect_x),
                    (self.do_scroll_y, self.effect_y),
                ]:
                    if enabled and isinstance(effect, NativeScrollEffect):
                        effect.discard_tap()
        return super().on_scroll_stop(touch, check_children)

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
        intent = touch.ud.get(self._get_uid())
        if intent is not None and intent.get('mode') == 'scroll':
            self.clear_preview()
        return result

    def on_touch_up(self, touch):
        self.clear_preview()
        return super().on_touch_up(touch)
