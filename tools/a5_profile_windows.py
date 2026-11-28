"""Isolated CI real OS drags; never foreground a local user application."""

import ctypes
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import traceback

assert os.environ.get('GITHUB_ACTIONS') == 'true', (
    'CI only; no local foreground control'
)
assert sys.platform == 'win32'
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from kivy.config import Config

Config.set('graphics', 'width', '900')
Config.set('graphics', 'height', '700')
# Match the delivered entry point: its frame policy must run before Window
# instantiates Kivy's Clock, which reads maxfps only at construction.
from nte_gear_optimizer_app.app import ComparisonApp
from kivy.clock import Clock
from kivy.core.window import Window

OUT = Path('build/a5_profile_windows')
OUT.mkdir(parents=True, exist_ok=False)


class PerformanceProbe(ComparisonApp):
    def on_start(self):
        assert Clock._max_fps == Config.getint('graphics', 'maxfps'), (
            'Benchmark initialized Clock before app frame policy'
        )
        self.actions = self.scenario()
        self.failure = None
        self.drag_error = None
        self.blocks = []
        self.flips = 0
        self.first_motion_types = []
        self.hover_uids_seen = set()
        Window.bind(on_motion=self.record_motion_type)
        Window.bind(on_flip=self.flipped)
        Clock.schedule_once(self.advance, 1)

    def record_motion_type(self, window, kind, touch):
        # A small first-event proof, not one allocation per movement.
        if len(self.first_motion_types) < 12 and kind in ('begin', 'end'):
            self.first_motion_types.append(
                {
                    'uid': touch.uid,
                    'event': kind,
                    'is_touch': touch.is_touch,
                    'type_id': touch.type_id,
                }
            )
        if not touch.is_touch:
            self.hover_uids_seen.add(touch.uid)

    def flipped(self, *args):
        self.flips += 1

    def advance(self, dt):
        try:
            if self.drag_error:
                raise RuntimeError(self.drag_error)
            delay = next(self.actions)
        except StopIteration:
            self.finish()
        except Exception:
            self.failure = traceback.format_exc()
            self.finish()
        else:
            Clock.schedule_once(self.advance, delay)

    def drag(self, up):
        # Obtain the client origin on the UI thread, inject actual OS mouse
        # messages from a separate timer so a slow UI cannot pace the input.
        from ctypes import wintypes

        api = ctypes.windll.user32
        api.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        api.FindWindowW.restype = wintypes.HWND
        api.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        api.SetForegroundWindow.argtypes = [wintypes.HWND]
        api.SetForegroundWindow.argtypes = [wintypes.HWND]
        api.GetForegroundWindow.restype = wintypes.HWND
        hwnd = api.FindWindowW(None, self.title)
        assert hwnd
        api.SetForegroundWindow(hwnd)
        assert api.GetForegroundWindow() == hwnd, (
            'Isolated CI app window has no foreground focus'
        )
        origin = wintypes.POINT(0, 0)
        assert api.ClientToScreen(hwnd, ctypes.byref(origin))
        api.SetForegroundWindow(hwnd)
        x, y = self.scroll.to_window(self.scroll.x, self.scroll.y)
        width, height = self.scroll.size
        start_y = origin.y + Window.height - (y + height * (0.25 if up else 0.75))
        end_y = origin.y + Window.height - (y + height * (0.75 if up else 0.25))
        screen_x = round(origin.x + x + width * 0.75)

        def gesture():
            try:
                api.SetCursorPos(screen_x, round(start_y))
                time.sleep(0.08)
                api.mouse_event(0x0002, 0, 0, 0, 0)
                started = time.perf_counter()
                for i in range(1, 97):
                    deadline = started + i / 120
                    time.sleep(max(0, deadline - time.perf_counter()))
                    api.SetCursorPos(
                        screen_x, round(start_y + (end_y - start_y) * i / 96)
                    )
                api.mouse_event(0x0004, 0, 0, 0, 0)
            except Exception:
                self.drag_error = traceback.format_exc()

        threading.Thread(target=gesture, daemon=True).start()

    def tap(self, widget):
        from ctypes import wintypes

        api = ctypes.windll.user32
        api.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        api.FindWindowW.restype = wintypes.HWND
        api.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        api.SetForegroundWindow.argtypes = [wintypes.HWND]
        api.GetForegroundWindow.restype = wintypes.HWND
        hwnd = api.FindWindowW(None, self.title)
        assert hwnd
        api.SetForegroundWindow(hwnd)
        assert api.GetForegroundWindow() == hwnd, (
            'Isolated CI app window has no foreground focus'
        )
        origin = wintypes.POINT(0, 0)
        assert api.ClientToScreen(hwnd, ctypes.byref(origin))
        x, y = widget.to_window(widget.center_x, widget.center_y)
        point = (round(origin.x + x), round(origin.y + Window.height - y))

        def action():
            try:
                api.SetCursorPos(*point)
                time.sleep(0.08)
                api.mouse_event(0x0002, 0, 0, 0, 0)
                time.sleep(0.04)
                api.mouse_event(0x0004, 0, 0, 0, 0)
            except Exception:
                self.drag_error = traceback.format_exc()

        threading.Thread(target=action, daemon=True).start()

    def scenario(self):
        # Establish a manual DAMAGE/ANG fixture outside measured gestures;
        # all measurements use real Windows mouse drags, never scroll setters.
        self.vm.set_override('ProfileType', 'DAMAGE')
        self.vm.set_override('ScalingStat', 'ANG')
        for page in range(4):
            self.vm.step = page
            self.render()
            yield 1.2
            experiments = (
                [
                    (True, mode)
                    for mode in [
                        'BASE',
                        'FREEZE',
                        'DEFER',
                        'BOTH',
                        'BOTH',
                        'DEFER',
                        'FREEZE',
                        'BASE',
                    ]
                ]
                if os.environ.get('NTE_A6_GC_COMPARE') == '1'
                else [
                    (value, None)
                    for value in (
                        [False, False]
                        if os.environ.get('NTE_A5_COMPARE') == '1'
                        else [True, False, False, True]
                    )
                ]
            )
            if os.environ.get('NTE_A6_PROFILE_COMPARE') == '1':
                experiments = [(True, 'BASE'), (True, 'BASE')]
            maintenance_order = (
                [False, True, True, False, True, False, False, True]
                if os.environ.get('NTE_A6_MAINTENANCE_COMPARE') == '1'
                else None
            )
            if maintenance_order is not None:
                experiments = [(True, 'BASE')] * len(maintenance_order)
            for block_index, (enabled, gc_mode) in enumerate(experiments):
                if maintenance_order is not None:
                    self.debug.defer_input_flush_on_scroll = maintenance_order[
                        block_index
                    ]
                before_flush_skips = self.debug.input_flush_skips
                self.debug.scroll_observer.metrics.finish()
                if hasattr(self.debug, 'frame_profiler'):
                    self.debug.frame_profiler.enabled = enabled
                if gc_mode is not None:
                    self.debug.gc_policy.request_mode(gc_mode)
                    yield 0.8
                    assert self.debug.gc_policy.mode == gc_mode, {
                        'active_touches': list(self.active_touches),
                        'metric_current': self.debug.scroll_observer.metrics.current,
                        'first_motion_types': self.first_motion_types,
                    }
                    assert self.debug.gc_policy.requested is None
                before = len(self.debug.scroll_observer.metrics.recent)
                self.drag(False)
                yield 2.3
                self.drag(True)
                yield 2.3
                self.debug.scroll_observer.metrics.finish()
                yield 0.3
                gestures = list(self.debug.scroll_observer.metrics.recent)[before:]
                assert any(
                    g.get('status') == 'MEASURED_GL_FLIP_PROXY' for g in gestures
                ), (page, gestures)
                if enabled:
                    from a6_check_attribution import check_attribution

                    for gesture in gestures:
                        if gesture.get('status') == 'MEASURED_GL_FLIP_PROXY':
                            check_attribution(gesture['frame_profile'])
                if maintenance_order is not None:
                    assert (
                        (self.debug.input_flush_skips > before_flush_skips)
                        if maintenance_order[block_index]
                        else (self.debug.input_flush_skips == before_flush_skips)
                    )
                self.blocks.append(
                    {
                        'page': page,
                        'gc_mode': gc_mode,
                        'defer_input_flush': self.debug.defer_input_flush_on_scroll,
                        'input_flush_skips_delta': self.debug.input_flush_skips
                        - before_flush_skips,
                        'profiling': enabled,
                        'gestures': deepcopy(gestures),
                    }
                )
            self.capture_view(OUT, 'page_' + str(page))
        if os.environ.get('NTE_A6_GC_MEMORY') == '1':
            self.memory_samples = []
            self.debug.gc_policy.request_mode('BOTH')
            yield 0.8
            memory_start_count = self.debug.gc_policy.deferred_gestures
            for i in range(200):
                self.drag(bool(i % 2))
                yield 2.3
                if i in (19, 99, 199):
                    self.debug.scroll_observer.metrics.finish()
                    yield 0.3
                    from a6_memory import rss_bytes

                    self.memory_samples.append(
                        {
                            'gestures': i + 1,
                            'rss_bytes': rss_bytes(),
                            'gc': self.debug.gc_policy.snapshot(),
                        }
                    )
            assert self.debug.gc_policy.deferred_gestures - memory_start_count >= 200
            values = [s['rss_bytes'] for s in self.memory_samples]
            assert values[-1] <= values[1] + max(8 * 1024 * 1024, values[1] * 0.05), (
                values
            )

    def finish(self):
        summary = self.debug.scroll_observer.summary()
        measured = summary['measured_gesture_count']
        result = {
            'status': 'MEASURED' if not self.failure and measured >= 6 else 'FAIL',
            'source_commit': subprocess.check_output(
                ['git', 'rev-parse', 'HEAD'], text=True
            ).strip(),
            'platform': 'windows',
            'first_motion_types': self.first_motion_types,
            'hover_uid_count': len(self.hover_uids_seen),
            'active_touches_at_end': list(self.active_touches),
            'effective_clock_maxfps': Clock._max_fps,
            'configured_maxfps': Config.getint('graphics', 'maxfps'),
            'frozen_baseline': os.environ.get('NTE_A4_FROZEN_BASELINE') == '1',
            'measurement_driver_sha256': __import__('hashlib')
            .sha256(Path(__file__).read_bytes())
            .hexdigest(),
            'selector_actual_os_mouse': self.active_selector is None,
            'failure': self.failure,
            'scroll_summary': summary,
            'profiling_blocks': self.blocks,
            'memory_samples': getattr(self, 'memory_samples', []),
            'gc_policy': self.debug.gc_policy.snapshot(),
            'idle_flips_in_two_seconds': getattr(
                self, 'idle_flips_in_two_seconds', None
            ),
            'scope': 'Isolated Windows runner OS input; GL flip proxy; not Samsung device.',
        }
        for name, value in [
            ('result.json', result),
            ('events.json', self.debug.journal.events()),
        ]:
            with (OUT / name).open('x', encoding='utf-8', newline='\n') as f:
                json.dump(value, f, ensure_ascii=False, indent=2)
        Window.screenshot(name=str(OUT / 'after_gestures.png'))
        self.stop()


app = PerformanceProbe()
app.run()
result = json.loads((OUT / 'result.json').read_text(encoding='utf-8'))
assert result['status'] == 'MEASURED', result
