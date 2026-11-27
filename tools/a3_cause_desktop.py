"""CI-only pre-fix reproduction via real operating-system mouse input."""

import ctypes
import json
import os
from pathlib import Path
import sys
import traceback

if os.environ.get('GITHUB_ACTIONS') != 'true':
    raise SystemExit('Only on isolated CI; never foreground a local user application')

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from kivy.config import Config

Config.set('graphics', 'width', '900')
Config.set('graphics', 'height', '700' if sys.platform == 'win32' else '850')
from kivy.clock import Clock
from kivy.core.window import Window
from nte_gear_optimizer_app.app import ComparisonApp
from nte_gear_optimizer_app.diagnostic_trace import InputTrace

out = Path(sys.argv[1]).resolve()
out.mkdir(parents=True, exist_ok=False)


def native_button(widget, pressed):
    x, y = widget.to_window(widget.center_x, widget.center_y)
    if sys.platform == 'win32':
        from ctypes import wintypes

        api = ctypes.windll.user32
        api.FindWindowW.restype = wintypes.HWND
        api.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        api.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        api.SetForegroundWindow.argtypes = [wintypes.HWND]
        handle = api.FindWindowW(None, ComparisonApp.title)
        assert handle, 'CI window absent'
        origin = wintypes.POINT(0, 0)
        assert api.ClientToScreen(handle, ctypes.byref(origin))
        api.SetForegroundWindow(handle)
        api.SetCursorPos(int(origin.x + x), int(origin.y + Window.height - y))
        api.mouse_event(0x0002 if pressed else 0x0004, 0, 0, 0, 0)
    else:
        x11 = ctypes.CDLL('libX11.so.6')
        xtst = ctypes.CDLL('libXtst.so.6')
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        display = x11.XOpenDisplay(None)
        assert display
        xtst.XTestFakeMotionEvent.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_ulong,
        ]
        xtst.XTestFakeButtonEvent.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_int,
            ctypes.c_ulong,
        ]
        x11.XFlush.argtypes = [ctypes.c_void_p]
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        xtst.XTestFakeMotionEvent(
            display, -1, int(Window.left + x), int(Window.top + Window.height - y), 0
        )
        xtst.XTestFakeButtonEvent(display, 1, int(pressed), 0)
        x11.XFlush(display)
        x11.XCloseDisplay(display)


class CauseProbe(ComparisonApp):
    def render(self):
        super().render()
        if hasattr(self, 'trace'):
            self.trace.attach_tree(self.root_box)

    def on_start(self):
        self.trace = InputTrace(self, lambda row: None)
        self.trace.attach_window(Window)
        self.trace.attach_tree(self.root_box)
        self.actions = self.scenario()
        self.result = {'status': 'PENDING', 'platform': sys.platform}
        Clock.schedule_once(self.advance, 1)

    def advance(self, _dt):
        try:
            delay = next(self.actions)
        except StopIteration:
            self.finish()
        except Exception:
            self.result = {
                'status': 'CAUSE_NOT_CONFIRMED_STOP',
                'stacktrace': traceback.format_exc(),
            }
            self.finish()
        else:
            Clock.schedule_once(self.advance, delay)

    def finish(self):
        for name, value in [
            ('result.json', self.result),
            ('events.json', list(self.trace.events)),
        ]:
            with (out / name).open('x', encoding='utf-8', newline='\n') as f:
                json.dump(value, f, ensure_ascii=False, indent=2)
        self.stop()

    def click(self, widget):
        native_button(widget, True)
        Clock.schedule_once(lambda dt: native_button(widget, False), 0.05)

    def choose(self, label, value):
        widget = self.selector_widgets[label]
        self.scroll.scroll_to(widget, padding=30)
        yield 0.8
        self.click(widget)
        yield 0.8
        option = next(w for key, name, w in self.selector_rows if key == value)
        self.click(option)
        yield 0.8
        assert self.selector_specs[label][1] == value

    def scenario(self):
        yield from self.choose('Leistungstyp', 'DAMAGE')
        yield from self.choose('Skalierung', 'ANG')
        yield from self.choose('Krit möglich?', 'TRUE')
        yield from self.choose('Bruch relevant?', 'FALSE')
        yield from self.choose('Zyklusreaktion', 'NONE')
        self.click(self.next_button)
        yield 0.8
        self.click(self.next_button)
        yield 0.8
        assert self.vm.step == 2
        target = self.inputs[('y', 'CritDamagePP')]
        self.scroll.scroll_to(target, padding=30)
        yield 1
        self.trace.emit('reproduction_attempt', target=self.trace.describe(target))
        begin = len(self.trace.events)
        self.click(target)
        yield 1
        accepted = [
            r for r in list(self.trace.events)[begin:] if r['event'] == 'touch_accepted'
        ]
        hidden = [
            r
            for r in accepted
            if not r['widget']['tree_visible'] or not r['widget']['enabled']
        ]
        assert not target.focus, 'Expected pre-fix blocked field instead received focus'
        assert hidden, ('No hidden/disabled consuming widget recorded', accepted)
        assert any(r['widget']['in_white_subtree'] for r in hidden), hidden
        self.capture_view(out, 'h01_before_bottom_field')
        self.result = {
            'status': 'EXPECTED_FAIL_CONFIRMED',
            'target': self.trace.describe(target),
            'target_focused': target.focus,
            'first_consuming_widget': accepted[0]['widget'],
            'hidden_consumers': hidden,
        }
        yield 0.1


app = CauseProbe()
app.run()
assert app.result['status'] == 'EXPECTED_FAIL_CONFIRMED', app.result
print(
    'Pre-fix H01 EXPECTED FAIL reproduced with real OS mouse; hidden white-base subtree consumed it'
)
