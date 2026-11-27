"""Isolated CI real OS drags; never foreground a local user application."""

import ctypes
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
from kivy.clock import Clock
from kivy.core.window import Window
from nte_gear_optimizer_app.app import ComparisonApp

OUT = Path('build/a4_performance_windows')
OUT.mkdir(parents=True, exist_ok=False)


class PerformanceProbe(ComparisonApp):
    def on_start(self):
        self.actions = self.scenario()
        self.failure = None
        self.drag_error = None
        self.blocks = []
        self.flips = 0
        Window.bind(on_flip=self.flipped)
        Clock.schedule_once(self.advance, 1)

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
        # The unmodified selection screen is long enough for reproducible
        # down/up gestures. Do not inject model values or call scroll_to.
        from nte_gear_optimizer_app import texts as T

        self.tap(self.selector_widgets[T.UI['character']])
        yield 1
        assert self.active_selector is not None, 'OS mouse did not open selector'
        self.capture_view(OUT, 'selector_actual_os_mouse')
        self.tap(self.active_selector[-1])
        yield 0.8
        assert self.active_selector is None
        if os.environ.get('NTE_A4_FROZEN_BASELINE') == '1':
            for _ in range(4):
                self.drag(False)
                yield 2.1
                self.drag(True)
                yield 2.1
            self.debug.scroll_observer.metrics.finish()
            yield 0.3
            return
        for enabled in [True, False, False, True]:
            self.debug.scroll_observer.metrics.finish()
            self.debug.journal.enabled = enabled
            before_seq = self.debug.journal.seq
            before_count = len(self.debug.scroll_observer.metrics.recent)
            for _ in range(2):
                self.drag(False)
                yield 2.1
                self.drag(True)
                yield 2.1
            self.debug.scroll_observer.metrics.finish()
            yield 0.3
            after_seq = self.debug.journal.seq
            if not enabled:
                assert after_seq == before_seq, (before_seq, after_seq)
            self.blocks.append(
                {
                    'logging': enabled,
                    'seq_before': before_seq,
                    'seq_after': after_seq,
                    'gestures': list(self.debug.scroll_observer.metrics.recent)[
                        before_count:
                    ],
                }
            )
        self.debug.journal.enabled = True
        # Let all kinetic motion finish, then count actual GL flips at rest.
        yield 4
        before_idle = self.flips
        yield 2
        self.idle_flips_in_two_seconds = self.flips - before_idle

    def finish(self):
        summary = self.debug.scroll_observer.summary()
        measured = summary['measured_gesture_count']
        result = {
            'status': 'MEASURED' if not self.failure and measured >= 6 else 'FAIL',
            'source_commit': subprocess.check_output(
                ['git', 'rev-parse', 'HEAD'], text=True
            ).strip(),
            'platform': 'windows',
            'frozen_baseline': os.environ.get('NTE_A4_FROZEN_BASELINE') == '1',
            'measurement_driver_sha256': __import__('hashlib')
            .sha256(Path(__file__).read_bytes())
            .hexdigest(),
            'selector_actual_os_mouse': self.active_selector is None,
            'failure': self.failure,
            'scroll_summary': summary,
            'logging_blocks': self.blocks,
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
