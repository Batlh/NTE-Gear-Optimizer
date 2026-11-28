"""Reversible GC experiment, default BASE until native benefit is established.

Python 3.14.2 (Android) and 3.14.10 (desktop) differ in generational threshold
semantics. Use the shared APIs, never pretend disable() pauses only old GC:
DEFER suspends *all automatic cyclic GC*, reference counting remains active.
Pending cyclic work is collected at idle, with bounded diagnostic history.
https://docs.python.org/3.14/library/gc.html
"""

import gc
import time
from collections import deque

DEFAULT_MODE = 'BASE'
MODES = ('BASE', 'FREEZE', 'DEFER', 'BOTH')


class GestureGCPolicy:
    def __init__(self, busy, api=gc, clock=time.perf_counter):
        self.api, self.clock, self.busy = api, clock, busy
        self.mode = 'BASE'
        self.requested = DEFAULT_MODE if DEFAULT_MODE != 'BASE' else None
        self.freeze_owned = self.pause_owned = False
        self.initial_enabled = api.isenabled()
        self.closed = False
        self.pending_cleanup = False
        self.deferred_gestures = self.idle_collections = self.freeze_calls = 0
        self.pause_started = None
        self.max_pause_ms = 0
        self.operations = deque(maxlen=32)
        self.status = 'BASE_NO_GC_CHANGE'

    def request_mode(self, mode):
        if mode not in MODES:
            raise ValueError('Unknown GC experiment mode')
        self.requested = mode

    def collect_idle(self):
        if self.busy():
            raise RuntimeError('Never collect cyclic garbage during a touch or inertia')
        start = self.clock()
        collected = self.api.collect(2)
        self.idle_collections += 1
        self.operations.append(
            {
                'operation': 'collect_idle',
                'ms': (self.clock() - start) * 1000,
                'collected': collected,
            }
        )

    def thaw_owned(self):
        if self.freeze_owned:
            self.api.unfreeze()
            self.freeze_owned = False

    def idle(self):
        if self.closed or self.busy():
            return
        self.end()
        if self.requested is not None:
            self.end()
            self.thaw_owned()
            mode, self.requested = self.requested, None
            self.mode = mode
            if not self.initial_enabled:
                self.status = 'EXTERNAL_GC_DISABLED_UNCHANGED'
                return
            # Same reset for every CI trial arm, outside the measured window.
            self.collect_idle()
            if mode in ('FREEZE', 'BOTH'):
                if self.api.get_freeze_count():
                    self.status = 'EXTERNAL_FREEZE_NOT_MODIFIED'
                else:
                    start = self.clock()
                    self.api.freeze()
                    self.freeze_calls += 1
                    self.freeze_owned = True
                    self.operations.append(
                        {
                            'operation': 'freeze_idle',
                            'ms': (self.clock() - start) * 1000,
                        }
                    )
                    self.status = 'OWNED_STARTUP_FREEZE'
            else:
                self.status = 'TRIAL_READY'
            self.pending_cleanup = False
        elif self.pending_cleanup and self.initial_enabled:
            self.pending_cleanup = False
            self.collect_idle()

    def begin(self):
        if self.closed or self.mode not in ('DEFER', 'BOTH') or self.pause_owned:
            return
        if self.initial_enabled and self.api.isenabled():
            self.api.disable()
            self.pause_owned = True
            self.pause_started = self.clock()
            self.deferred_gestures += 1

    def end(self, force=False):
        if self.busy() and not force:
            return
        if self.pause_owned:
            self.max_pause_ms = max(
                self.max_pause_ms, (self.clock() - self.pause_started) * 1000
            )
            self.api.enable()
            self.pause_owned = False
            self.pause_started = None
            self.pending_cleanup = True

    def snapshot(self):
        return {
            'mode': self.mode,
            'requested': self.requested,
            'status': self.status,
            'automatic_gc_paused': self.pause_owned,
            'automatic_gc_enabled': self.api.isenabled(),
            'deferred_gestures': self.deferred_gestures,
            'idle_collections': self.idle_collections,
            'freeze_calls': self.freeze_calls,
            'freeze_owned': self.freeze_owned,
            'frozen_objects': self.api.get_freeze_count(),
            'gc_count': self.api.get_count(),
            'max_pause_ms': self.max_pause_ms,
            'recent_idle_operations': list(self.operations),
            'scope': 'Only cyclic automatic GC is deferred, all generations; refcounting unchanged. Manual external collect() is not intercepted. BASE is default pending measured benefit.',
        }

    def stop(self):
        self.end(force=True)
        self.thaw_owned()
        self.closed = True
        self.pending_cleanup = False
