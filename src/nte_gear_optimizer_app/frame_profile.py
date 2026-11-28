"""Buffered CPU-side frame spans, not GPU timestamps or physical presentation."""

from collections import deque
from functools import wraps
import statistics, math, time
from .frame_attribution import Attribution, CATEGORIES

CURRENT = None
PHASES = ('layout', 'canvas_build', 'keyboard_probe', 'viewport')


def summary(values):
    if not values:
        return None
    s = sorted(values)
    return {
        'n': len(s),
        'median': round(statistics.median(s), 4),
        'p95': round(s[math.ceil(0.95 * len(s)) - 1], 4),
        'max': round(s[-1], 4),
        'sum': round(sum(s), 4),
    }


def phase(name):
    def decorate(fn):
        @wraps(fn)
        def call(*args, **kwargs):
            p = CURRENT
            if p is None or not p.recording():
                return fn(*args, **kwargs)
            t = p.clock()
            try:
                return fn(*args, **kwargs)
            finally:
                p.add(name, (p.clock() - t) * 1000)
                p.attribution.span(name, t, p.clock())

        return call

    return decorate


def install_layout_hook():
    from kivy.uix.boxlayout import BoxLayout

    if not getattr(BoxLayout.do_layout, '_nte_profiled', False):
        wrapped = phase('layout')(BoxLayout.do_layout)
        wrapped._nte_profiled = True
        BoxLayout.do_layout = wrapped


def inventory(root):
    widgets = list(root.walk())
    seen = set()
    types = {}

    def visit(node):
        if id(node) in seen:
            return
        seen.add(id(node))
        name = type(node).__name__
        types[name] = types.get(name, 0) + 1
        for child in getattr(node, 'children', []):
            visit(child)

    visit(root.canvas)
    return {
        'widgets': len(widgets),
        'widget_types': {
            n: sum(type(w).__name__ == n for w in widgets)
            for n in sorted({type(w).__name__ for w in widgets})
        },
        'canvas_instructions': len(seen),
        'instruction_types': types,
        'scope': 'Current attached root only, sampled outside gestures; cached pages not attached are excluded.',
    }


class FrameProfiler:
    columns = [
        'elapsed_ms',
        'interval_ms',
        'layout_ms',
        'canvas_build_ms',
        'keyboard_probe_ms',
        'viewport_ms',
        'draw_dispatch_ms',
        'flip_call_wall_ms',
        'layout_calls',
        'canvas_build_calls',
    ]

    def __init__(self, window, active, clock=time.perf_counter):
        global CURRENT
        CURRENT = self
        self.window, self.active, self.clock = window, active, clock
        self.enabled = True
        self.attribution = Attribution(self.recording, clock)
        self.attribution_rows = deque(maxlen=1200)
        self.pages_seen = set()
        self.first_view = None
        self.runtime_hooks = None
        self.rows = deque(maxlen=1200)
        self.total = 0
        self.pending = {}
        self.started = clock()
        self.last = None
        self.draw_start = None
        self.draw_ms = 0
        self.cached_inventory = {}
        self.next_root = None
        self.hook_status = 'NOT_INSTALLED'
        if window is not None:
            window.bind(on_draw=self.before_draw, on_flip=self.before_flip)
            self.original_flip = window.flip
            try:
                window.flip = self.flip
                self.hook_status = 'ACTUAL_WINDOW_FLIP_CALL'
            except AttributeError, TypeError:
                self.hook_status = 'UNVERIFIED_FLIP_NOT_WRITABLE'

    def recording(self):
        return self.enabled and self.active()

    def add(self, name, ms):
        old = self.pending.get(name, (0, 0))
        self.pending[name] = (old[0] + ms, old[1] + 1)

    def begin(self):
        self.attribution.reset()
        self.attribution_rows.clear()
        self.view_label = None
        self.first_view = None
        self.rows.clear()
        self.pending.clear()
        self.total = 0
        self.started = self.clock()
        self.last = None
        self.draw_start = None

    def note_view(self, label):
        if self.view_label is None:
            self.view_label = label
            self.first_view = label not in self.pages_seen

    def queue_inventory(self, root, page=None):
        self.next_root = root
        self.next_page = page

    def idle_inventory(self):
        if self.next_root is not None and not self.active():
            self.cached_inventory = inventory(self.next_root)
            self.cached_inventory['page'] = self.next_page
            self.next_root = None

    def before_draw(self, *args):
        self.draw_start = self.clock() if self.recording() else None

    def before_flip(self, *args):
        if self.draw_start is not None:
            self.draw_ms = (self.clock() - self.draw_start) * 1000
        if self.hook_status != 'ACTUAL_WINDOW_FLIP_CALL' and self.recording():
            self.record(None)

    def flip(self, *args, **kwargs):
        if not self.recording():
            return self.original_flip(*args, **kwargs)
        t = self.clock()
        try:
            return self.original_flip(*args, **kwargs)
        finally:
            self.record((self.clock() - t) * 1000)

    def record(self, flip_ms):
        now = self.clock()

        def get(n):
            return self.pending.get(n, (0, 0))

        row = [
            1000 * (now - self.started),
            1000 * (now - self.last) if self.last is not None else None,
            *(get(n)[0] for n in PHASES),
            self.draw_ms,
            flip_ms,
            get('layout')[1],
            get('canvas_build')[1],
        ]
        lower = self.last if self.last is not None else self.started
        if self.draw_start is not None:
            self.attribution.span('draw', self.draw_start, now - (flip_ms or 0) / 1000)
        if flip_ms is not None:
            self.attribution.span('flip', now - flip_ms / 1000, now)
        attribution_row = self.attribution.frame(lower, now)
        attribution_row['interval_available'] = self.last is not None
        self.attribution_rows.append(attribution_row)
        self.rows.append([round(v, 4) if isinstance(v, float) else v for v in row])
        self.total += 1
        self.last = now
        self.pending.clear()
        self.draw_start = None
        self.draw_ms = 0

    def finish(self):
        rows = list(self.rows)
        result = {
            'enabled': self.enabled,
            'hook_status': self.hook_status,
            'frames_observed': self.total,
            'rows_retained': len(rows),
            'raw_truncated': self.total > len(rows),
            'columns': self.columns,
            'statistics': {
                name: summary([r[i] for r in rows if r[i] is not None])
                for i, name in enumerate(self.columns)
            },
            'inventory': self.cached_inventory,
            'attribution': {
                'schema': 1,
                'categories': CATEGORIES,
                'callback_names': self.attribution.names[:],
                'frames': list(self.attribution_rows),
                'first_scroll_on_view': self.first_view,
                'view_label': getattr(self, 'view_label', None),
                'runtime_hooks': self.runtime_hooks.status
                if self.runtime_hooks
                else 'NOT_INSTALLED',
                'texture_scope': 'CoreLabel.refresh new texture identities only; not all GPU allocations/image uploads. First-scroll flag refers to current page, not physical visibility.',
                'accounting': 'Exclusive interval union with priority; unassigned includes scheduler/idle/driver gaps and observer overhead. Clock totals are inclusive; do not add them again. Overflow makes attribution incomplete.',
            },
            'rows': rows,
            'scope': 'Buffered CPU wall spans; BoxLayout calls; draw dispatch includes canvas submission; flip includes driver/OS wait, not GPU execution timing. Inclusive/nested spans must not be summed as exclusive costs.',
        }
        if rows and getattr(self, 'view_label', None) is not None:
            self.pages_seen.add(self.view_label)
        self.rows.clear()
        self.attribution_rows.clear()
        self.pending.clear()
        self.total = 0
        self.last = None
        return result

    def stop(self):
        global CURRENT
        if self.runtime_hooks is not None:
            self.runtime_hooks.stop()
        if self.window is not None:
            self.window.unbind(on_draw=self.before_draw, on_flip=self.before_flip)
            if self.hook_status == 'ACTUAL_WINDOW_FLIP_CALL':
                self.window.flip = self.original_flip
        if CURRENT is self:
            CURRENT = None
