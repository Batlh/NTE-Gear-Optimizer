"""CI OS-mouse reachability matrix, live layout guard and debug integration."""

import json
import ctypes
import os
from pathlib import Path
import sys
import traceback
import time

assert os.environ.get('GITHUB_ACTIONS') == 'true', (
    'Isolated CI only; never control a local window'
)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from kivy.config import Config

Config.set('graphics', 'width', '900')
Config.set('graphics', 'height', '700' if sys.platform == 'win32' else '850')
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from nte_gear_optimizer_app.app import ComparisonApp
from nte_gear_optimizer_app.viewmodel import ComparisonViewModel
from nte_gear_optimizer_app.debug_journal import JSON_MARKER


# OS input implementation is copied mechanically from the verified pre-fix
# driver at generation time. It does not dispatch directly to Kivy widgets.
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
        if pressed is not None:
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
        if pressed is not None:
            xtst.XTestFakeButtonEvent(display, 1, int(pressed), 0)
        x11.XFlush(display)
        x11.XCloseDisplay(display)


out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=False)


def intersection(a, b):
    x, y, w, h = a
    xx, yy, ww, hh = b
    left, bottom = max(x, xx), max(y, yy)
    return (
        left,
        bottom,
        max(0, min(x + w, xx + ww) - left),
        max(0, min(y + h, yy + hh) - bottom),
    )


class FieldProbe(ComparisonApp):
    def on_start(self):
        self.evidence = []
        self.result = {'status': 'PENDING'}
        self.actions = self.scenarios()
        Clock.schedule_once(self.advance, 0.8)

    def advance(self, dt):
        try:
            delay = next(self.actions)
        except StopIteration:
            self.result = {'status': 'PASS', 'checks': len(self.evidence)}
            self.finish()
        except Exception:
            self.result = {'status': 'FAIL', 'stacktrace': traceback.format_exc()}
            self.finish()
        else:
            Clock.schedule_once(self.advance, delay)

    def finish(self):
        # The debug tool must also explain its own failing export, not just
        # leave a test assertion. This is read-only diagnostic evidence.
        events = self.debug.journal.events()
        (out / 'journal_events.json').write_text(
            json.dumps(events, ensure_ascii=False, indent=2),
            encoding='utf-8',
            newline='\n',
        )
        if self.active_debug:
            self.result['active_debug_buttons'] = list(self.active_debug[1])
            self.result['active_debug_texts'] = [
                str(getattr(w, 'text', ''))
                for w in self.active_debug[0].walk()
                if getattr(w, 'text', '')
            ]
        if self.result['status'] != 'PASS':
            self.capture_view(out, 'failure_view')
        for name, value in [
            ('result.json', self.result),
            ('evidence.json', self.evidence),
        ]:
            (out / name).write_text(
                json.dumps(value, ensure_ascii=False, indent=2),
                encoding='utf-8',
                newline='\n',
            )
        self.stop()

    def click(self, widget):
        self.click_start_sequence = self.debug.trace.sequence
        self.click_start_time = time.monotonic()
        # Windows SDL receives mouse-motion asynchronously. Do not post the
        # down event in the same event-loop turn as SetCursorPos: the proven
        # failed export clicked the previous button's coordinates instead.
        self.evidence.append({'os_click_requested': self.debug.trace.describe(widget)})
        native_button(widget, None)
        Clock.schedule_once(lambda dt: native_button(widget, True), 0.12)
        Clock.schedule_once(lambda dt: native_button(widget, False), 0.20)

    def wait_click(self, predicate, description):
        # The CI VM can stall an SDL frame on disk I/O. A fixed sleep expired
        # before motion_end in run46009343844. Wait for the actual OS release
        # and requested outcome, without repeating the click or setting focus.
        deadline = self.click_start_time + 3
        while True:
            released = any(
                row['seq'] > self.click_start_sequence and row['event'] == 'motion_end'
                for row in self.debug.trace.events
            )
            if released and predicate():
                self.evidence.append(
                    {
                        'observed_os_click': description,
                        'seconds': round(time.monotonic() - self.click_start_time, 3),
                    }
                )
                return
            assert time.monotonic() < deadline, (
                'OS click deadline',
                description,
                released,
            )
            yield 0.05

    def clipped(self, widget):
        box = [*widget.to_window(*widget.pos), *widget.size]
        parent = widget.parent
        visited = set()
        while parent is not None and parent not in visited:
            visited.add(parent)
            if isinstance(parent, ScrollView):
                box = intersection(box, [*parent.to_window(*parent.pos), *parent.size])
            parent = parent.parent
        return intersection(box, [0, 0, Window.width, Window.height])

    def guard(self, case, step):
        widgets = list(self.root_box.walk())
        active = [
            w
            for w in widgets
            if isinstance(w, (TextInput, Button))
            and self.debug.trace.describe(w)['tree_visible']
            and not w.disabled
        ]
        failures = []
        for hidden in widgets:
            description = self.debug.trace.describe(hidden)
            if description['tree_visible'] and description['enabled']:
                continue
            a = self.clipped(hidden)
            if a[2] <= 0 or a[3] <= 0:
                continue
            for target in active:
                overlap = intersection(a, self.clipped(target))
                if overlap[2] > 0.5 and overlap[3] > 0.5:
                    failures.append(
                        {
                            'hidden': description,
                            'target': self.debug.trace.describe(target),
                        }
                    )
        assert not failures, failures
        self.evidence.append({'case': case, 'step': step, 'static_overlap': 'PASS'})

    def check_fields(self, case, step):
        self.vm.step = step
        self.render()
        yield 0.7
        # Removed subtrees are deliberately not reachable/visible inputs.
        fields = [
            (key, w)
            for key, w in self.inputs.items()
            if self.debug.trace.describe(w)['tree_visible']
        ]
        assert fields, (case, step)
        for key, widget in fields:
            self.scroll.scroll_to(widget, padding=30)
            yield 0.5
            self.guard(case, step)
            self.click(widget)
            yield from self.wait_click(
                lambda: [k for k, w in self.inputs.items() if w.focus] == [key],
                ':'.join(key),
            )
            focused = [k for k, w in self.inputs.items() if w.focus]
            assert focused == [key], (case, step, key, focused)
            self.evidence.append(
                {
                    'case': case,
                    'step': step,
                    'field': ':'.join(key),
                    'os_mouse_focus': 'PASS',
                }
            )
        self.capture_view(out, case + '_step' + str(step + 1) + '_bottom')
        yield 0.1

    def export_only(self):
        self.vm = ComparisonViewModel()
        for key, value in {
            'ProfileType': 'DAMAGE',
            'ScalingStat': 'ANG',
            'CritEligible': 'FALSE',
            'BreakEligible': 'FALSE',
            'CycleType': 'NONE',
        }.items():
            self.vm.set_override(key, value)
        self.vm.item_x = {'ScalingPercentPP': '0', 'UniversalPP': '25😝60'}
        self.vm.item_y = {'ScalingPercentPP': '0', 'UniversalPP': '2.560'}
        self.vm.ark_level = '80😝8'
        self.vm.choose_ark('ARK_ECHOES_ON_HOLD')
        self.render()
        yield 0.7
        self.debug.test_exception()
        self.debug.toggle_overlay()
        self.click(self.inputs[('level', 'ArkLevel')])
        yield 0.5
        self.debug.menu()
        yield 0.7
        self.click(self.active_debug[1]['Debug-Bericht exportieren'])
        yield 0.7
        self.capture_view(out, 'privacy_notice')
        assert 'Fortfahren' in self.active_debug[1]
        self.click(self.active_debug[1]['Fortfahren'])
        yield 1.2
        self.capture_view(out, 'export_after_click')
        assert 'Schließen' in self.active_debug[1]
        exported = max((Path.home() / 'Downloads').glob('NTE_Debugbericht_*.txt'))
        saved = exported.read_text(encoding='utf-8')
        assert json.loads(saved.split(JSON_MARKER)[1])['format'] == 'NTE_DEBUG_V1'
        (out / 'NTE_Debugbericht_export_only.txt').write_bytes(exported.read_bytes())
        self.evidence.append({'real_export_only': 'PASS'})
        yield 0.1

    def scenarios(self):
        if os.environ.get('NTE_A3_EXPORT_ONLY') == '1':
            yield from self.export_only()
            return
        # Pairwise reduction: every scaling, all applicability flags both on
        # and off, known/unknown scaling, and a released guide profile.
        cases = [
            ('manual_ang', 'ANG', 'FALSE', 'FALSE', 'NONE'),
            ('manual_lp', 'LP', 'TRUE', 'TRUE', 'NOVA'),
            ('manual_ver', 'VER', 'TRUE', 'FALSE', 'NONE'),
            ('manual_unknown', 'UNBEKANNT', 'FALSE', 'TRUE', 'BLOSSOM'),
            ('manual_base_atk', 'BASIS_ANG', 'FALSE', 'FALSE', 'NONE'),
            ('manual_other_scale', 'SONSTIGE', 'FALSE', 'FALSE', 'NONE'),
        ]
        for name, scale, crit, brk, cycle in cases:
            self.vm = ComparisonViewModel()
            for key, value in {
                'ProfileType': 'DAMAGE',
                'ScalingStat': scale,
                'CritEligible': crit,
                'BreakEligible': brk,
                'CycleType': cycle,
            }.items():
                self.vm.set_override(key, value)
            yield from self.check_fields(name, 1)
            yield from self.check_fields(name, 2)
        # An actual catalog branch and its unchanged release flags.
        row = next(
            r
            for r in self.vm.catalog['Branches']
            if r.get('ScalingStat') in ('ANG', 'LP', 'VER')
            and r.get('ProfileType') in ('DAMAGE', 'HEAL', 'SHIELD')
        )
        profile = next(
            r
            for r in self.vm.catalog['Profiles']
            if r['BuildProfileID'] == row['BuildProfileID']
        )
        self.vm.choose_character(profile['CharacterID'])
        self.vm.choose_profile(profile['BuildProfileID'])
        self.vm.choose_branch(row['ComparisonBranchID'])
        yield from self.check_fields('guide_' + row['ComparisonBranchID'], 1)
        yield from self.check_fields('guide_' + row['ComparisonBranchID'], 2)
        # Both directions of the white-base conditional subtree, including
        # focus and top-edge alignment when just one side displays a hint.
        self.vm = ComparisonViewModel()
        self.vm.set_override('ProfileType', 'DAMAGE')
        self.vm.set_override('ScalingStat', 'ANG')
        self.vm.set_override('CritEligible', 'FALSE')
        self.vm.set_override('BreakEligible', 'FALSE')
        self.vm.set_override('CycleType', 'NONE')
        self.vm.item_x['ScalingPercentPP'] = '0'
        self.vm.item_y['ScalingPercentPP'] = '10'
        yield from self.check_fields('white_attached', 2)
        assert self.white_box.parent is self.body
        assert any(
            row['event'] == 'focus'
            and row.get('focused')
            and row.get('widget', {}).get('field') == 'white:WhitePanelBase'
            for row in self.debug.journal.events()
        ), 'Dynamically attached white-base focus was not journalled'

        self.inputs[('y', 'ScalingPercentPP')].text = '0'
        yield 0.5
        assert self.white_box.parent is None
        self.guard('white_removed', 2)
        start_sequence = self.debug.journal.seq
        self.inputs[('y', 'ScalingPercentPP')].text = '10'
        yield 0.5
        assert self.white_box.parent is self.body
        white = self.inputs[('white', 'WhitePanelBase')]
        self.scroll.scroll_to(white, padding=30)
        yield 0.5
        self.click(white)
        yield 0.55
        assert white.focus
        assert any(
            row['seq'] > start_sequence
            and row['event'] == 'focus'
            and row.get('focused')
            and row.get('widget', {}).get('field') == 'white:WhitePanelBase'
            for row in self.debug.journal.events()
        )
        self.inputs[('y', 'ScalingPercentPP')].text = '0'
        yield 0.5
        assert self.white_box.parent is None
        self.guard('white_removed_again', 2)

        self.inputs[('x', 'UniversalPP')].text = '2.560'
        yield 0.5
        left = self.inputs[('x', 'UniversalPP')]
        right = self.inputs[('y', 'UniversalPP')]
        assert self.input_hints[('x', 'UniversalPP')].text
        assert abs(left.top - right.top) < 0.5, (left.top, right.top)
        self.scroll.scroll_to(left, padding=30)
        yield 0.5
        self.capture_view(out, 'paired_hint_top_aligned')
        left.text = '0'
        right.text = '2.560'
        yield 0.5
        assert abs(left.top - right.top) < 0.5
        self.capture_view(out, 'paired_hint_right_top_aligned')
        left.text = '25😝60'
        yield 0.5
        assert self.input_hints[('x', 'UniversalPP')].text
        self.capture_view(out, 'numeric_emoji_help')
        self.vm.step = 0
        self.render()
        self.inputs[('level', 'ArkLevel')].text = '80😝8'
        yield 0.5
        assert self.input_hints[('level', 'ArkLevel')].text
        self.capture_view(out, 'ark_level_emoji_no_ark')
        self.vm.choose_ark('ARK_ECHOES_ON_HOLD')
        self.render()
        yield 0.5
        assert self.input_hints[('level', 'ArkLevel')].text
        self.capture_view(out, 'ark_level_emoji_selected_ark')
        self.debug.test_exception()
        self.debug.toggle_overlay()
        self.click(self.inputs[('level', 'ArkLevel')])
        yield 0.5
        self.capture_view(out, 'touch_overlay')
        self.debug.menu()
        yield 0.5
        self.capture_view(out, 'debug_menu')
        self.click(self.active_debug[1]['Debug-Bericht exportieren'])
        yield from self.wait_click(
            lambda: self.active_debug and 'Fortfahren' in self.active_debug[1],
            'Fortfahren',
        )
        assert 'Fortfahren' in self.active_debug[1]
        self.click(self.active_debug[1]['Fortfahren'])
        yield from self.wait_click(
            lambda: self.active_debug and 'Schließen' in self.active_debug[1],
            'Schließen',
        )
        assert 'Schließen' in self.active_debug[1]
        exported = max((Path.home() / 'Downloads').glob('NTE_Debugbericht_*.txt'))
        saved = exported.read_text(encoding='utf-8')
        assert json.loads(saved.split(JSON_MARKER)[1])['format'] == 'NTE_DEBUG_V1'
        assert str(Path.home()) not in saved
        assert any(
            getattr(w, 'text', None) == str(exported)
            for w in self.active_debug[0].walk()
        )
        (out / 'NTE_Debugbericht_desktop_saved.txt').write_bytes(exported.read_bytes())
        self.evidence.append(
            {
                'desktop_export_via_os_mouse': 'PASS',
                'saved_report_json': 'PASS',
                'destination_displayed': 'PASS',
            }
        )
        self.capture_view(out, 'debug_export_saved')
        self.active_debug[0].dismiss()
        self.active_debug = None
        # An actual private journal report, not fabricated expected events.
        report = self.debug.journal.report(self.debug.device(), self.debug.state())
        (out / 'NTE_Debugbericht_desktop.txt').write_text(
            report, encoding='utf-8', newline='\n'
        )
        payload = json.loads(report.split(JSON_MARKER)[1])
        events = payload['events']
        assert any(e['event'] == 'input' and e['raw'] == '2.560' for e in events)
        assert any(
            e['event'] == 'exception' and 'NTE_A3_TEST_EXCEPTION' in e['stacktrace']
            for e in events
        )
        assert any(e['event'] == 'touch_accepted' for e in events)
        self.evidence.append(
            {
                'report_roundtrip': 'PASS',
                'test_exception': 'PASS',
                'top_alignment': 'PASS',
            }
        )
        yield 0.1


app = FieldProbe()
app.run()
assert app.result['status'] == 'PASS', app.result
