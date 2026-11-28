"""Bounded main-thread spans; disjoint frame attribution, not GPU timing."""

from array import array
import gc
import threading

# Higher priority claims nested time first. All categories are disjoint in
# exclusive_ms; inclusive callback totals are reported separately.
CATEGORIES = (
    'clock',
    'input',
    'draw',
    'flip',
    'layout',
    'canvas_build',
    'keyboard_probe',
    'viewport',
    'texture',
    'gc',
)
CAPACITY = 2048
CALLBACKS = 128


class Attribution:
    def __init__(self, active, clock):
        self.active, self.clock = active, clock
        self.thread = threading.get_ident()
        self.starts = array('d', [0.0]) * CAPACITY
        self.ends = array('d', [0.0]) * CAPACITY
        self.kinds = array('i', [0]) * CAPACITY
        self.details = array('i', [0]) * CAPACITY
        self.names = ['OVERFLOW_OR_UNNAMED']
        self.name_ids = {'OVERFLOW_OR_UNNAMED': 0}
        self.callback_ms = array('d', [0.0]) * CALLBACKS
        self.callback_calls = array('i', [0]) * CALLBACKS
        self.gc_start = array('d', [-1.0]) * 3
        self.kind_ids = {name: i for i, name in enumerate(CATEGORIES)}
        self.enabled = True
        self.accounting = False
        self.gc_hook = self.gc_event
        self.gc_installed = False
        self.reset()

    def reset(self):
        self.used = self.overflow = self.input_calls = self.texture_changes = 0
        self.clock_calls = 0
        self.gc_counts = [0, 0, 0]
        for i in range(CALLBACKS):
            self.callback_ms[i] = self.callback_calls[i] = 0
        for i in range(3):
            self.gc_start[i] = -1

    def recording(self):
        return (
            self.enabled
            and not self.accounting
            and threading.get_ident() == self.thread
            and self.active()
        )

    def name_id(self, name):
        value = self.name_ids.get(name)
        if value is None:
            if len(self.names) == CALLBACKS:
                return 0
            value = len(self.names)
            self.name_ids[name] = value
            self.names.append(name)
        return value

    def span(self, kind, start, end, callback_id=0):
        if not self.recording():
            return
        if kind == 'clock':
            self.clock_calls += 1
            self.callback_calls[callback_id] += 1
            self.callback_ms[callback_id] += max(0, end - start) * 1000
        elif kind == 'input':
            self.input_calls += 1
        if self.used == CAPACITY:
            self.overflow += 1
            return
        i = self.used
        self.starts[i], self.ends[i] = start, end
        self.kinds[i] = self.kind_ids[kind]
        self.details[i] = callback_id
        self.used += 1

    def gc_event(self, event, info):
        if not self.recording():
            return
        gen = info['generation']
        if gen not in (0, 1, 2):
            return
        if event == 'start':
            self.gc_start[gen] = self.clock()
        elif self.gc_start[gen] >= 0:
            self.gc_counts[gen] += 1
            self.span('gc', self.gc_start[gen], self.clock(), gen)
            self.gc_start[gen] = -1

    def install_gc(self):
        if not self.gc_installed:
            gc.callbacks.append(self.gc_hook)
            self.gc_installed = True

    def stop(self):
        if self.gc_installed:
            gc.callbacks.remove(self.gc_hook)
            self.gc_installed = False

    def frame(self, lower, upper):
        self.accounting = True
        try:
            return self._frame(lower, upper)
        finally:
            self.accounting = False

    def _frame(self, lower, upper):
        # Allocation/sorting occurs once at frame end, never per move event.
        events = []
        inclusive = [0.0] * len(CATEGORIES)
        gc_events = []
        for i in range(self.used):
            a, b = max(lower, self.starts[i]), min(upper, self.ends[i])
            if b > a:
                kind = self.kinds[i]
                inclusive[kind] += (b - a) * 1000
                events.append((a, kind, 1))
                events.append((b, kind, -1))
                if CATEGORIES[kind] == 'gc':
                    gc_events.append([self.details[i], (b - a) * 1000])
        events.sort()
        active = [0] * len(CATEGORIES)
        exclusive = [0.0] * len(CATEGORIES)
        last = lower
        for stamp, kind, delta in events:
            for priority in range(len(CATEGORIES) - 1, -1, -1):
                if active[priority]:
                    exclusive[priority] += (stamp - last) * 1000
                    break
            active[kind] += delta
            last = stamp
        top = sorted(
            (i for i in range(len(self.names)) if self.callback_calls[i]),
            key=lambda i: self.callback_ms[i],
            reverse=True,
        )[:5]
        result = {
            'exclusive_ms': exclusive,
            'inclusive_ms': inclusive,
            'unassigned_ms': max(0, (upper - lower) * 1000 - sum(exclusive)),
            'clock_calls': self.clock_calls,
            'input_calls': self.input_calls,
            'gc_counts': self.gc_counts[:],
            'gc_events': gc_events,
            'texture_changes': self.texture_changes,
            'clock_top5': [
                [i, self.callback_calls[i], self.callback_ms[i]] for i in top
            ],
            'overflow': self.overflow,
        }
        self.reset()
        return result
