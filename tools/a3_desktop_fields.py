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
# Use the delivered app startup order before creating Clock/Window.
from nte_gear_optimizer_app.app import ComparisonApp
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
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

        def press_after_observed_motion(dt):
            if self.result.get('status') == 'FAIL':
                return False
            x, y = widget.to_window(widget.center_x, widget.center_y)
            actual = Window.mouse_pos
            if abs(actual[0] - x) > 2 or abs(actual[1] - y) > 2:
                if time.monotonic() - self.click_start_time >= 2.5:
                    # Let the existing3s outcome deadline retain the failure.
                    self.evidence.append(
                        {'mouse_motion_not_ready': list(actual), 'requested': [x, y]}
                    )
                    return False
                return True
            self.evidence.append(
                {'observed_sdl_pointer_before_down': list(actual), 'requested': [x, y]}
            )
            native_button(widget, True)
            Clock.schedule_once(lambda _: native_button(widget, False), 0.08)
            return False

        Clock.schedule_interval(press_after_observed_motion, 0.01)

    def position_for_hold(self, widget):
        native_button(widget, None)
        deadline = time.monotonic() + 2.5
        while True:
            x, y = widget.to_window(widget.center_x, widget.center_y)
            actual = Window.mouse_pos
            if abs(actual[0] - x) <= 2 and abs(actual[1] - y) <= 2:
                self.evidence.append(
                    {'hold_pointer_ready': list(actual), 'requested': [x, y]}
                )
                return
            assert time.monotonic() < deadline, (
                'SDL pointer not ready for hold',
                list(actual),
                [x, y],
            )
            yield 0.01

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
        yield from self.wait_click(
            lambda: self.active_debug and 'Fortfahren' in self.active_debug[1],
            'export_only_privacy',
        )
        self.capture_view(out, 'privacy_notice')
        assert 'Fortfahren' in self.active_debug[1]
        self.click(self.active_debug[1]['Fortfahren'])
        yield from self.wait_click(
            lambda: self.active_debug and 'Schließen' in self.active_debug[1],
            'export_only_saved',
        )
        self.capture_view(out, 'export_after_click')
        assert 'Schließen' in self.active_debug[1]
        exported = max((Path.home() / 'Downloads').glob('NTE_Debugbericht_*.txt'))
        saved = exported.read_text(encoding='utf-8')
        short = json.loads(saved.split(JSON_MARKER)[1])
        assert short['format'] == 'NTE_DEBUG_V1'
        assert short['report_mode'] == 'SHORT'
        assert len(saved.encode('utf-8')) < 200_000
        assert len(short['events']) <= 300
        (out / 'NTE_Debugbericht_export_only.txt').write_bytes(exported.read_bytes())
        self.evidence.append({'real_export_only': 'PASS'})
        yield 0.1

    def scenarios(self):
        yield 0.5
        from a5_header_geometry import verify_header

        self.evidence.append(verify_header(self))
        self.capture_view(out, 'header_centered')
        if os.environ.get('NTE_A3_EXPORT_ONLY') == '1':
            yield from self.export_only()
            return
        from a5_desktop_touch_cases import cases as h01_cases

        yield from h01_cases(self, native_button)
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

        # Actual OS navigation must reuse all existing fields. Zero changes
        # their values without invoking render or replacing a widget.
        body_before = self.body
        fields_before = dict(self.inputs)
        self.click(self.back_button)
        yield from self.wait_click(lambda: self.vm.step == 1, 'reuse_back')
        self.click(self.next_button)
        yield from self.wait_click(lambda: self.vm.step == 2, 'reuse_forward')
        assert self.body is body_before
        assert all(self.inputs.get(k) is w for k, w in fields_before.items())
        zero = self.zero_buttons[0]
        self.scroll.scroll_to(zero, padding=30)
        yield 0.5
        boundary = self.debug.journal.seq
        yield from self.position_for_hold(zero)
        native_button(zero, True)
        yield 0.04
        assert zero.state == 'down', 'No optical down feedback while held'
        native_button(zero, False)
        yield 0.6
        after_zero = self.debug.journal.events()
        assert any(
            r['event'] == 'zero_bonus' and r['seq'] > boundary for r in after_zero
        )
        assert not any(
            r['event'] == 'performance'
            and r.get('operation') == 'render'
            and r['seq'] > boundary
            for r in after_zero
        )
        assert self.body is body_before
        assert all(self.inputs.get(k) is w for k, w in fields_before.items())
        self.evidence.append(
            {
                'page_reuse_back_forward': 'PASS',
                'zero_without_render': 'PASS',
                'held_button_feedback': 'PASS',
            }
        )

        self.inputs[('x', 'UniversalPP')].text = '2.560'
        yield 0.5
        left = self.inputs[('x', 'UniversalPP')]
        right = self.inputs[('y', 'UniversalPP')]
        assert self.input_hints[('x', 'UniversalPP')].text
        assert abs(left.top - right.top) < 0.5, (left.top, right.top)
        self.scroll.scroll_to(left, padding=30)
        yield 0.5
        self.capture_view(out, 'paired_hint_top_aligned')
        # Check actual rendered text, not just the foreground property: a
        # wrongly appended canvas Color can tint otherwise correct properties.
        self.dismiss_keyboard()
        yield 0.3
        self.capture_view(out, 'design_input_contrast')
        from PIL import Image

        if sys.platform == 'win32':
            # ANGLE's glReadPixels produces an all-black screenshot in this
            # Windows CI setup. Capture the actual OS client area instead,
            # using explicit client/screen geometry (no title-bar guess).
            from PIL import ImageGrab
            from ctypes import wintypes

            api = ctypes.windll.user32
            api.FindWindowW.restype = wintypes.HWND
            api.GetForegroundWindow.restype = wintypes.HWND
            handle = api.FindWindowW(None, ComparisonApp.title)
            assert handle and api.GetForegroundWindow() == handle
            api.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
            api.ClientToScreen.argtypes = [
                wintypes.HWND,
                ctypes.POINTER(wintypes.POINT),
            ]
            client = wintypes.RECT()
            origin = wintypes.POINT(0, 0)
            assert api.GetClientRect(handle, ctypes.byref(client))
            assert api.ClientToScreen(handle, ctypes.byref(origin))
            image = ImageGrab.grab(
                bbox=(
                    origin.x,
                    origin.y,
                    origin.x + client.right,
                    origin.y + client.bottom,
                )
            ).convert('RGB')
            image.save(out / 'design_input_client_pixels.png')
        else:
            Window.screenshot(name=str(out / 'design_input_pixels.png'))
            shot = max(out.glob('design_input_pixels*.png'))
            image = Image.open(shot).convert('RGB')
        x, y = left.to_window(left.x, left.y)
        sx, sy = image.width / Window.width, image.height / Window.height
        region = image.crop(
            (
                int((x + 8) * sx),
                int((Window.height - y - left.height + 5) * sy),
                int((x + left.width - 8) * sx),
                int((Window.height - y - 5) * sy),
            )
        )
        bright = sum(min(pixel) >= 180 for pixel in region.getdata())
        assert bright >= 8, ('Input text lost foreground contrast', bright)
        assert self.debug_button.height >= 48
        self.evidence.append(
            {'rendered_input_foreground': 'PASS', 'debug_touch_height': 'PASS'}
        )
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
        # Footer primary button is outside the ScrollView preview: its own
        # pressed canvas must visibly change on the actual OS down event.
        normal_fill = self.next_button.fill.source
        yield from self.position_for_hold(self.next_button)
        native_button(self.next_button, True)
        yield 0.08
        assert self.next_button.state == 'down'
        assert self.next_button.fill.source != normal_fill
        self.capture_view(out, 'primary_button_pressed')
        native_button(self.next_button, False)
        yield 0.6
        assert self.vm.step == 1
        self.click(self.back_button)
        yield from self.wait_click(lambda: self.vm.step == 0, 'primary_feedback_return')
        self.evidence.append({'primary_actual_pressed_fill': 'PASS'})
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
        short = json.loads(saved.split(JSON_MARKER)[1])
        assert short['format'] == 'NTE_DEBUG_V1'
        assert short['report_mode'] == 'SHORT'
        assert len(saved.encode('utf-8')) < 200_000
        assert len(short['events']) <= 300
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
        timings = [e for e in events if e['event'] == 'performance']
        assert timings and payload['performance_summary']['slowest_10']
        assert any(e['operation'] == 'render' for e in timings)
        assert any(e['operation'] == 'touch_to_response_frame' for e in timings)
        assert any(e['operation'] == 'export' for e in timings)
        assert all(
            isinstance(e['duration_ms'], (int, float))
            and isinstance(e['over_100_ms'], bool)
            for e in timings
        )
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
