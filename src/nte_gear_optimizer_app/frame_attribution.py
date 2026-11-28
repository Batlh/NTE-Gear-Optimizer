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
    'measurement',
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
        self.gc_lock = threading.RLock()
        self.gc_carry_start = array('d', [0.0]) * 32
        self.gc_carry_end = array('d', [0.0]) * 32
        self.gc_carry_gen = array('i', [0]) * 32
        self.gc_carry_used = self.gc_carry_overflow = 0
        self.gc_start = array('d', [-1.0]) * 3
        self.kind_ids = {name: i for i, name in enumerate(CATEGORIES)}
        self.enabled = True
        self.accounting = False
        self.next_spans = []
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
        # Include observer-induced GC too. During the sweep, carry its
        # completed interval into the next frame instead of recursively
        # modifying the interval list that is currently being accounted.
        if not self.enabled or not self.active():
            return
        gen = info['generation']
        if gen not in (0, 1, 2):
            return
        if event == 'start':
            self.gc_start[gen] = self.clock()
        elif self.gc_start[gen] >= 0:
            end = self.clock()
            off_ui = threading.get_ident() != self.thread
            if self.accounting or off_ui:
                with self.gc_lock:
                    i = self.gc_carry_used
                    if i < 32:
                        self.gc_carry_start[i] = self.gc_start[gen]
                        self.gc_carry_end[i] = end
                        self.gc_carry_gen[i] = gen + (3 if off_ui else 0)
                        self.gc_carry_used += 1
                    else:
                        self.gc_carry_overflow += 1
            else:
                self.gc_counts[gen] += 1
                self.span('gc', self.gc_start[gen], end, gen)
            self.gc_start[gen] = -1

    def install_gc(self):
        if not self.gc_installed:
            gc.callbacks.append(self.gc_hook)
            self.gc_installed = True

    def stop(self):
        if self.gc_installed:
            gc.callbacks.remove(self.gc_hook)
            self.gc_installed = False

    def drain_gc(self):
        with self.gc_lock:
            for i in range(self.gc_carry_used):
                tag = self.gc_carry_gen[i]
                self.gc_counts[tag % 3] += 1
                self.span('gc', self.gc_carry_start[i], self.gc_carry_end[i], tag)
            self.gc_carry_used = 0
            self.overflow += self.gc_carry_overflow
            self.gc_carry_overflow = 0

    def frame(self, lower, upper):
        self.drain_gc()
        self.accounting = True
        try:
            return self._frame(lower, upper)
        finally:
            self.accounting = False
            for kind, start, end, tag in self.next_spans:
                self.span(CATEGORIES[kind], start, end, tag)
            self.next_spans.clear()
            self.drain_gc()

    def _frame(self, lower, upper):
        # Allocation/sorting occurs once at frame end, never per move event.
        events = []
        future = []
        inclusive = [0.0] * len(CATEGORIES)
        gc_events = []
        gc_off_ui_events = 0
        for i in range(self.used):
            # Flip timestamp precedes observer bookkeeping. GC triggered by
            # that bookkeeping can already be pending but belongs to the next
            # physical flip interval; never discard it at the boundary.
            if self.ends[i] > upper:
                future.append(
                    (
                        self.kinds[i],
                        max(upper, self.starts[i]),
                        self.ends[i],
                        self.details[i],
                    )
                )
            a, b = max(lower, self.starts[i]), min(upper, self.ends[i])
            if b > a:
                kind = self.kinds[i]
                inclusive[kind] += (b - a) * 1000
                events.append((a, kind, 1))
                events.append((b, kind, -1))
                if CATEGORIES[kind] == 'gc':
                    gc_events.append([self.details[i] % 3, (b - a) * 1000])
                    gc_off_ui_events += int(self.details[i] >= 3)
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
            'gc_counts': [
                sum(event[0] == gen for event in gc_events) for gen in range(3)
            ],
            'gc_events': gc_events,
            'gc_off_ui_events': gc_off_ui_events,
            'texture_changes': self.texture_changes,
            'clock_top5': [
                [i, self.callback_calls[i], self.callback_ms[i]] for i in top
            ],
            'overflow': self.overflow,
        }
        self.reset()
        self.next_spans = future
        return result
