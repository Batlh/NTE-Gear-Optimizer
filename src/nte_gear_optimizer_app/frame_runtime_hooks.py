"""Reversible Kivy 2.3.2 observation hooks, including scheduled triggers.

ClockEvent.callback/weak_callback are public in Kivy _clock.pxd; on_schedule is
the scheduling notification in _clock.pyx. Preserve weak bound methods,
release_ref=False, callback identity comparisons, return values and exceptions.
Source: https://github.com/kivy/kivy/blob/2.3.2/kivy/_clock.pyx
"""

import functools
import weakref


class TimedCallback:
    def __init__(self, original, attribution, release_ref=True):
        self.weak = (
            weakref.ref(original.__self__)
            if release_ref
            and getattr(original, '__self__', None) is not None
            and hasattr(original, '__func__')
            else None
        )
        self.method_name = original.__func__.__name__ if self.weak is not None else None
        self.strong = None if self.weak is not None else original
        self.attribution = weakref.ref(attribution)
        fn = original.func if isinstance(original, functools.partial) else original
        self.name = (
            getattr(fn, '__module__', '')
            + '.'
            + getattr(fn, '__qualname__', type(fn).__name__)
        )
        self.index = attribution.name_id(self.name)

    def original(self):
        if self.weak is None:
            return self.strong
        target = self.weak()
        return getattr(target, self.method_name, None) if target is not None else None

    def __eq__(self, other):
        if isinstance(other, TimedCallback):
            other = other.original()
        value = self.original()
        return value is not None and value == other

    def __call__(self, dt):
        original = self.original()
        if original is None:
            return False
        p = self.attribution()
        if p is None or not p.recording():
            return original(dt)
        start = p.clock()
        try:
            return original(dt)
        finally:
            p.span('clock', start, p.clock(), self.index)


class RuntimeHooks:
    def __init__(self, profiler, clock, event_loop, core_label):
        self.profiler = profiler
        self.p = profiler.attribution
        self.clock, self.event_loop, self.core_label = clock, event_loop, core_label
        self.original_schedule = clock.on_schedule
        self.original_input = event_loop.post_dispatch_input
        self.original_refresh = core_label.refresh
        self.p.install_gc()

        def scheduled(event):
            self.wrap(event)
            return self.original_schedule(event)

        self.scheduled = scheduled
        clock.on_schedule = scheduled
        # Existing pending events and future/rescheduled triggers, not a costly
        # per-frame Clock.get_events scan. Scheduling may happen off-thread.
        for event in clock.get_events() + clock.get_before_frame_events():
            self.wrap(event)

        def input_dispatch(kind, touch):
            p = self.p
            if kind != 'update':
                return self.original_input(kind, touch)
            start = p.clock()
            try:
                return self.original_input(kind, touch)
            finally:
                p.span('input', start, p.clock())

        def refresh(label, *args, **kwargs):
            p = self.p
            if not p.recording():
                return self.original_refresh(label, *args, **kwargs)
            before = label.texture
            start = p.clock()
            try:
                return self.original_refresh(label, *args, **kwargs)
            finally:
                p.span('texture', start, p.clock())
                if label.texture is not None and label.texture is not before:
                    p.texture_changes += 1

        self.input_dispatch, self.refresh = input_dispatch, refresh
        event_loop.post_dispatch_input = input_dispatch
        core_label.refresh = refresh
        self.status = 'INSTALLED_CLOCK_INPUT_GC_CORELABEL'

    def wrap(self, event):
        cb = event.get_callback()
        if cb is None or isinstance(cb, TimedCallback):
            return
        timed = TimedCallback(cb, self.p, release_ref=bool(event.release_ref))
        event.callback = timed
        event.weak_callback = None

    def stop(self):
        self.p.enabled = False
        self.clock.on_schedule = self.original_schedule
        self.event_loop.post_dispatch_input = self.original_input
        self.core_label.refresh = self.original_refresh
        for event in self.clock.get_events() + self.clock.get_before_frame_events():
            cb = event.get_callback()
            if isinstance(cb, TimedCallback):
                event.callback = cb.original()
                event.weak_callback = None
                if event.callback is not None and event.release_ref:
                    event.release()
        self.p.stop()
