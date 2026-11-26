"""Thin Kivy bindings; no calculation formulas live in widgets."""

import os
import json
from pathlib import Path
from importlib.resources import files
from kivy.config import Config

Config.set('input', 'mouse', 'mouse,multitouch_on_demand')
Config.set('kivy', 'exit_on_escape', '0')
if os.environ.get('NTE_TEST_MODE') == 'smoke':
    Config.set('graphics', 'width', '900')
    Config.set(
        'graphics', 'height', '700' if __import__('sys').platform == 'win32' else '980'
    )
from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.modalview import ModalView
from kivy.graphics import Color, Rectangle
from kivy.uix.textinput import TextInput
from .viewmodel import ComparisonViewModel, numeric_hint
from . import texts as T

FONT = str(files('nte_gear_optimizer_app').joinpath('assets/DejaVuSans.ttf'))
LabelBase.register(name='NTEText', fn_regular=FONT, fn_bold=FONT)


class ComparisonApp(App):
    title = T.TITLE
    icon = str(
        files('nte_gear_optimizer_app').joinpath('assets/icons/kiwi_icon_512.png')
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.vm = ComparisonViewModel()
        self.inputs = {}
        self.white_box = None
        self.zero_buttons = []
        self.smoke_index = 0
        self.details_expanded = False
        self.clarification_expanded = False
        self.show_all_values = False
        self.input_hints = {}
        self.active_selector = None

    def label(self, text, size=17):
        label = Label(
            text=text,
            font_name='NTEText',
            font_size=sp(size),
            halign='left',
            valign='middle',
            size_hint_y=None,
        )
        label.bind(
            width=lambda widget, width: setattr(widget, 'text_size', (width, None))
        )
        label.bind(
            texture_size=lambda widget, size: setattr(
                widget, 'height', max(dp(42), size[1] + dp(12))
            )
        )
        return label

    def button(self, text, callback):
        button = Button(
            text=text,
            font_name='NTEText',
            font_size=sp(17),
            size_hint_y=None,
            height=dp(52),
            background_normal='',
            background_color=(0.12, 0.37, 0.48, 1),
        )
        button.bind(on_release=lambda *_: callback())
        return button

    def spinner(self, label, choices, current, callback):
        self.body.add_widget(self.label(label))
        mapping = {}
        for value, name in choices:
            unique = name
            index = 2
            while unique in mapping:
                unique = name + ' (' + str(index) + ')'
                index += 1
            mapping[unique] = value
        displayed = next(
            (name for name, value in mapping.items() if value == current), T.NO_CHOICE
        )
        # A bounded, opaque modal for EVERY selector: no nested dropdown
        # escaping behind the Android navigation bar or outer ScrollView.
        entries = sorted(
            mapping.items(), key=lambda pair: (pair[1] is not None, pair[0].casefold())
        )
        self.selector_specs[label] = (entries, current)
        widget = self.button(
            displayed, lambda: self.open_selector(label, entries, callback)
        )
        self.selector_widgets[label] = widget
        self.body.add_widget(widget)

    def open_selector(self, title, entries, callback):
        self.dismiss_keyboard()
        popup = ModalView(
            size_hint=(0.96, 0.90),
            auto_dismiss=False,
            background='',
            background_color=(0.08, 0.11, 0.15, 1),
        )
        layout = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(8))
        with layout.canvas.before:
            Color(0.08, 0.11, 0.15, 1)
            background = Rectangle(pos=layout.pos, size=layout.size)
        layout.bind(
            pos=lambda w, v: setattr(background, 'pos', v),
            size=lambda w, v: setattr(background, 'size', v),
        )
        layout.add_widget(self.label(title, 21))
        scroll = ScrollView(
            do_scroll_x=False, scroll_timeout=350, scroll_distance=dp(12)
        )
        rows = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(4))
        rows.bind(minimum_height=rows.setter('height'))
        self.selector_rows = []

        def select(value):
            popup.dismiss()
            self.active_selector = None
            callback(value)

        for name, value in entries:
            button = self.button(name, lambda value=value: select(value))
            rows.add_widget(button)
            self.selector_rows.append((value, name, button))
        scroll.add_widget(rows)
        layout.add_widget(scroll)
        cancel = self.button(
            'Abbrechen',
            lambda: (popup.dismiss(), setattr(self, 'active_selector', None)),
        )
        layout.add_widget(cancel)
        popup.add_widget(layout)
        self.active_selector = (title, popup, scroll, cancel)
        popup.open()

    def dismiss_keyboard(self):
        for widget in self.inputs.values():
            widget.focus = False

    def text_input(self, group, field, value):
        widget = TextInput(
            text=value or '',
            multiline=False,
            font_name='NTEText',
            font_size=sp(18),
            size_hint_y=None,
            height=dp(50),
            write_tab=False,
            # ScrollView can forward a short touch only after touch-up. Do not
            # let the global touch-up focus handler immediately close its IME.
            # Selection of another field and Done/navigation still dismiss it.
            unfocus_on_touch=False,
            input_type='text',
        )
        widget.bind(on_text_validate=lambda field: setattr(field, 'focus', False))
        widget.bind(
            focus=lambda field, focused: (
                Clock.schedule_once(
                    lambda dt: self.scroll.scroll_to(field, padding=dp(24)), 0.25
                )
                if focused
                else None
            )
        )
        if group == 'white':
            widget.bind(
                text=lambda _, value: setattr(self.vm, 'white_panel_base', value)
            )
        elif group == 'level':
            widget.bind(text=lambda _, value: setattr(self.vm, 'ark_level', value))
        else:
            widget.bind(text=lambda _, value: self.input_changed(group, field, value))
        self.inputs[(group, field)] = widget
        box = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(50))
        hint = Label(
            text='',
            font_name='NTEText',
            font_size=sp(14),
            halign='left',
            valign='middle',
            size_hint_y=None,
            height=0,
            color=(1, 0.75, 0.35, 1),
        )
        hint.bind(width=lambda _, width: setattr(hint, 'text_size', (width, None)))

        def resize(*_):
            hint.height = max(dp(32), hint.texture_size[1] + dp(8)) if hint.text else 0
            box.height = dp(50) + hint.height

        def validate(_, value):
            hint.text = numeric_hint(value) if group != 'level' else ''
            resize()

        hint.bind(texture_size=resize)
        widget.bind(text=validate)
        box.add_widget(widget)
        box.add_widget(hint)
        validate(widget, widget.text)
        self.input_hints[(group, field)] = hint
        return box

    def input_changed(self, group, field, value):
        self.vm.set_value(group, field, value)
        if field == 'ScalingPercentPP':
            self.update_white_visibility()

    def update_white_visibility(self):
        if self.white_box is not None:
            needed = self.vm.needs_white_base()
            self.white_box.height = (
                max(dp(112), self.white_box.minimum_height) if needed else 0
            )
            self.white_box.opacity = 1 if needed else 0
            self.white_box.disabled = not needed

    def build(self):
        Window.softinput_mode = 'below_target'
        Window.clearcolor = (0.065, 0.085, 0.11, 1)
        self.root_box = BoxLayout(orientation='vertical', padding=dp(16), spacing=dp(8))
        self.root_box.add_widget(self.label(T.LOGO + '   ' + T.TITLE, 23))
        self.root_box.add_widget(self.label(T.SUBTITLE, 14))
        self.progress = self.label('', 20)
        self.root_box.add_widget(self.progress)
        self.scroll = ScrollView(
            do_scroll_x=False, scroll_timeout=350, scroll_distance=dp(12)
        )
        self.body = BoxLayout(orientation='vertical', spacing=dp(10), size_hint_y=None)
        self.body.bind(minimum_height=self.body.setter('height'))
        self.scroll.add_widget(self.body)
        self.root_box.add_widget(self.scroll)
        footer = BoxLayout(spacing=dp(12), size_hint_y=None, height=dp(54))
        self.back_button = self.button(T.BACK, self.go_back)
        self.next_button = self.button(T.NEXT, self.go_next)
        footer.add_widget(self.back_button)
        footer.add_widget(self.next_button)
        self.root_box.add_widget(footer)
        self.root_box.add_widget(
            self.label(
                T.footer(
                    os.environ.get('NTE_TEST_MODE') == 'smoke',
                    os.environ.get('NTE_FONT_PROBE') == '1',
                ),
                14,
            )
        )
        self.render()
        return self.root_box

    def go_back(self):
        self.dismiss_keyboard()
        self.vm.back()
        self.render()

    def go_next(self):
        self.dismiss_keyboard()
        self.vm.next()
        if self.vm.step == 3:
            self.vm.calculate()
        self.render()

    def change(self, method, value):
        method(value)
        self.render()

    def profile_change(self, key, value):
        self.vm.set_override(key, value)
        self.render()

    def render(self):
        self.dismiss_keyboard()
        self.selector_specs = {}
        self.selector_widgets = {}
        self.jump_buttons = {}
        self.body.clear_widgets()
        self.inputs = {}
        self.input_hints = {}
        self.white_box = None
        self.zero_buttons = []
        self.progress.text = T.STEPS[self.vm.step]
        self.scroll.scroll_y = 1
        self.back_button.disabled = self.vm.step == 0
        self.next_button.text = T.NEXT if self.vm.step < 3 else T.UI['recalculate']
        if self.vm.step == 0:
            self.selection()
        elif self.vm.step in (1, 2):
            self.values_screen(parts=self.vm.step == 2)
        else:
            summary = self.vm.compact_display()
            if self.vm.last_result['engine'].get('Verdict') is None:
                leading, remaining = summary.split('\n\n' + T.CHANGED, 1)
                self.body.add_widget(self.label(leading.split('\n\nWas fehlt', 1)[0]))
                self.body.add_widget(self.label('Was fehlt', 21))
                for step, messages in self.vm.missing_groups():
                    self.body.add_widget(self.label(T.STEPS[step]))
                    button = self.button(
                        'Zu Schritt ' + str(step + 1),
                        lambda step=step: self.jump_to(step),
                    )
                    self.jump_buttons[step] = button
                    self.body.add_widget(button)
                    self.body.add_widget(self.label('\n'.join(messages)))
                # Place the jump immediately with the missing-input group;
                # guide/hints must not push it several screens down.
                remaining = T.CHANGED + remaining
                markers = [
                    remaining.index(marker)
                    for marker in ('\n\nGuide\n', '\n\n' + T.HINTS + '\n')
                    if marker in remaining
                ]
                split = min(markers) if markers else len(remaining)
                self.body.add_widget(self.label(remaining[:split]))
                self.body.add_widget(
                    self.button(
                        'Alle Werte zur Klärung'
                        if not self.clarification_expanded
                        else 'Klärungswerte einklappen',
                        self.toggle_clarification,
                    )
                )
                if self.clarification_expanded:
                    self.body.add_widget(self.label(self.vm.clarification_display()))
                self.body.add_widget(self.label(remaining[split:]))
            else:
                self.body.add_widget(self.label(summary))
            self.details_button = self.button(
                T.DETAILS_CLOSE if self.details_expanded else T.DETAILS_OPEN,
                self.toggle_details,
            )
            self.body.add_widget(self.details_button)
            if self.details_expanded:
                self.all_values_button = self.button(
                    T.SHOW_CHANGED if self.show_all_values else T.SHOW_ALL,
                    self.toggle_all_values,
                )
                self.body.add_widget(self.all_values_button)
                self.body.add_widget(
                    self.label(self.vm.details_display(self.show_all_values))
                )

    def jump_to(self, step):
        self.vm.jump_to(step)
        self.render()

    def toggle_clarification(self):
        self.clarification_expanded = not self.clarification_expanded
        self.render()

    def toggle_details(self):
        self.details_expanded = not self.details_expanded
        self.render()

    def toggle_all_values(self):
        self.show_all_values = not self.show_all_values
        self.render()

    def selection(self):
        self.spinner(
            T.UI['character'],
            [(None, T.NO_CHOICE)]
            + [
                (r['CharacterID'], r['CharacterName'])
                for r in self.vm.catalog['Characters']
            ],
            self.vm.character_id,
            lambda value: self.change(self.vm.choose_character, value),
        )
        self.spinner(
            T.UI['ark'],
            [(None, T.NO_CHOICE)]
            + [(r['ArkID'], r['ArkName']) for r in self.vm.catalog['Arks']],
            self.vm.ark_id,
            lambda value: self.change(self.vm.choose_ark, value),
        )
        self.body.add_widget(self.label(T.UI['ark_level']))
        self.body.add_widget(self.text_input('level', 'ArkLevel', self.vm.ark_level))
        self.spinner(
            T.UI['profile'],
            [(None, T.MANUAL)]
            + [
                (
                    r['BuildProfileID'],
                    r['Name']
                    + ' · '
                    + (
                        T.UI['legacy_profile']
                        if r['SourceStatus'] == 'NOT_VERIFIED_FOR_1_5'
                        else T.UI['new_profile']
                    ),
                )
                for r in self.vm.profiles()
            ],
            self.vm.profile_id,
            lambda value: self.change(self.vm.choose_profile, value),
        )
        if self.vm.branches():
            options = [(None, T.ALL_BRANCHES)] + [
                (
                    r['ComparisonBranchID'],
                    r.get('ScalingMechanismName', '').replace('_', ' ').title()
                    + ' · '
                    + T.TYPE_NAMES.get(r.get('ProfileType'), T.MESSAGES['unknown']),
                )
                for r in self.vm.branches()
            ]
            self.spinner(
                T.UI['branch'],
                options,
                self.vm.branch_id,
                lambda value: self.change(self.vm.choose_branch, value),
            )
        selected = next(
            (
                r
                for r in self.vm.branches()
                if r['ComparisonBranchID'] == self.vm.branch_id
            ),
            None,
        )
        if selected:
            self.body.add_widget(self.label(T.MESSAGES['source_old']))
            if selected.get('Condition'):
                self.body.add_widget(
                    self.label(T.MESSAGES['source_condition'] + selected['Condition'])
                )
        self.body.add_widget(self.label(T.ASSUMPTION))
        profile = self.vm.profile()
        # All-branch evaluation keeps each branch's released flags independent.
        if self.vm.branches() and self.vm.branch_id is None:
            self.body.add_widget(self.label(T.UI['all_branch_note']))
        else:
            self.spinner(
                T.UI['type'],
                list(T.TYPE_NAMES.items()),
                profile.get('ProfileType'),
                lambda value: self.profile_change('ProfileType', value),
            )
            self.spinner(
                T.UI['scale'],
                list(T.SCALE_NAMES.items()),
                profile.get('ScalingStat'),
                lambda value: self.profile_change('ScalingStat', value),
            )
            if profile.get('ProfileType') == 'DAMAGE':
                self.spinner(
                    T.UI['crit'],
                    list(T.BOOL_NAMES.items()),
                    profile.get('CritEligible'),
                    lambda value: self.profile_change('CritEligible', value),
                )
                self.spinner(
                    T.UI['break'],
                    list(T.BOOL_NAMES.items()),
                    profile.get('BreakEligible'),
                    lambda value: self.profile_change('BreakEligible', value),
                )
                self.spinner(
                    T.UI['cycle'],
                    list(T.CYCLE_NAMES.items()),
                    profile.get('CycleType'),
                    lambda value: self.profile_change('CycleType', value),
                )
        self.body.add_widget(self.label(T.ARK_WARNING))

    def zero(self, name, parts):
        self.vm.zero_group(name, parts)
        self.render()

    def values_screen(self, parts=False):
        self.body.add_widget(self.label(T.SWAP_NOTE if parts else T.CURRENT_NOTE))
        for name, fields in self.vm.groups(parts).items():
            self.body.add_widget(self.label(T.GROUP_NAMES[name], 21))
            if parts or name != 'scale':
                zero = self.button(T.ZERO, lambda name=name: self.zero(name, parts))
                self.zero_buttons.append(zero)
                self.body.add_widget(zero)
            if parts:
                self.body.add_widget(
                    self.label(T.PART_X + '                         ' + T.PART_Y)
                )
            for field in fields:
                self.body.add_widget(
                    self.label(
                        T.field_label(
                            field, self.vm.profile().get('ScalingStat'), parts
                        )
                    )
                )
                row = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(52))
                row.bind(
                    minimum_height=lambda row, height: setattr(
                        row, 'height', max(dp(52), height)
                    )
                )
                if parts:
                    row.add_widget(
                        self.text_input('x', field, self.vm.item_x.get(field))
                    )
                    row.add_widget(
                        self.text_input('y', field, self.vm.item_y.get(field))
                    )
                else:
                    row.add_widget(
                        self.text_input('current', field, self.vm.current.get(field))
                    )
                self.body.add_widget(row)
        if parts and 'ScaleDirect' in self.vm.fields():
            self.white_box = BoxLayout(orientation='vertical', size_hint_y=None)
            self.white_box.bind(
                minimum_height=lambda *_: self.update_white_visibility()
            )
            self.white_box.add_widget(self.label(T.FIELD_LABELS['WhitePanelBase']))
            self.white_box.add_widget(
                self.text_input('white', 'WhitePanelBase', self.vm.white_panel_base)
            )
            self.body.add_widget(self.white_box)
            self.update_white_visibility()
        if not self.vm.fields():
            self.body.add_widget(self.label(T.UI['missing_profile']))
        if parts:
            self.body.add_widget(self.label(T.UI['parts_hint']))

    def on_start(self):
        from kivy.utils import platform

        if platform == 'android':
            from .android_ci import install_probe

            install_probe(self)
        if os.environ.get('NTE_TEST_MODE') == 'smoke':
            Clock.schedule_once(self.smoke, 0.8)

    def smoke(self, _dt):
        out = Path(os.environ['NTE_TEST_OUTPUT'])
        out.mkdir(parents=True, exist_ok=True)
        if self.smoke_index == 0:
            self.vm.choose_character('ELYMS')
            self.vm.choose_ark('ARK_ECHOES_ON_HOLD')
            self.vm.ark_level = '80'
            for key, value in {
                'ProfileType': 'DAMAGE',
                'ScalingStat': 'ANG',
                'CritEligible': 'FALSE',
                'BreakEligible': 'FALSE',
                'CycleType': 'NONE',
            }.items():
                self.vm.set_override(key, value)
            self.render()
        elif self.smoke_index == 1:
            for button in list(self.zero_buttons):
                button.dispatch('on_release')
            self.inputs[('current', 'ScaleDirect')].text = '100'
        elif self.smoke_index == 2:
            for button in list(self.zero_buttons):
                button.dispatch('on_release')
            self.inputs[('x', 'ScaleDirect')].text = '10'
            self.inputs[('y', 'ScaleDirect')].text = '20'
        elif self.smoke_index == 3:
            result = self.vm.last_result
            assert (
                result['engine']['Verdict'] == 'BETTER'
                and result['engine']['VerdictRatio'] == '1.100000000'
            ), result
            assert result['engine']['Deltas']['ScaleDirect'] == '10'
            report = {
                'result': result,
                'display': self.vm.display(),
                'python': __import__('sys').version,
                'frozen': bool(getattr(__import__('sys'), 'frozen', False)),
                'kivy': __import__('kivy').__version__,
            }
            with (out / 'smoke_result.json').open(
                'x', encoding='utf-8', newline='\n'
            ) as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
        Clock.schedule_once(lambda dt: self.capture_and_advance(out), 0.7)

    def capture_view(self, out, name):
        if __import__('sys').platform == 'win32':
            # ANGLE's default-framebuffer readback can be black after swap.
            # Capture the actual isolated CI window, not an invented rendering.
            import ctypes
            from ctypes import wintypes
            from PIL import ImageGrab

            find = ctypes.windll.user32.FindWindowW
            find.restype = wintypes.HWND
            find.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
            handle = find(None, self.title)
            assert handle, 'CI application window not found'
            ImageGrab.grab(window=handle).save(out / (name + '.png'))
            self.root_box.export_to_png(str(out / ('canvas_' + name + '.png')))
        else:
            Window.screenshot(name=str(out / (name + '.png')))

    def capture_and_advance(self, out):
        self.capture_view(out, 'step_' + str(self.smoke_index + 1))
        if self.smoke_index == 3:
            assert not self.details_expanded
            self.details_button.dispatch('on_release')
            assert self.details_expanded and not self.show_all_values
            Clock.schedule_once(lambda dt: self.capture_details(out), 0.7)
            return
        self.next_button.trigger_action(duration=0)
        self.smoke_index += 1
        Clock.schedule_once(self.smoke, 0.7)

    def capture_details(self, out):
        self.capture_view(out, 'details_expanded')
        self.all_values_button.dispatch('on_release')
        assert self.show_all_values
        self.details_button.dispatch('on_release')
        assert not self.details_expanded
        self.vm.step = 1
        self.render()
        self.inputs[('current', 'ScaleDirect')].text = '2.560'
        assert self.input_hints[('current', 'ScaleDirect')].text == T.THOUSANDS_HINT
        result = self.vm.calculate()
        assert (
            result['engine']['Verdict'] is None
            and result['part_deltas']['ScaleDirect'] == '10'
        )
        assert T.THOUSANDS_HINT in self.vm.compact_display()
        Clock.schedule_once(lambda dt: self.capture_input_help(out), 0.7)

    def capture_input_help(self, out):
        self.capture_view(out, 'input_help')
        self.vm.set_value('current', 'ScaleDirect', '100')
        self.vm.set_value('current', 'CritRatePP', '2.560')
        assert self.vm.calculate()['engine']['Verdict'] == 'BETTER'
        report = {
            'details_toggle': 'PASS',
            'show_all_toggle': 'PASS',
            'thousands_field_hint': 'PASS',
            'known_delta_retained': 'PASS',
            'irrelevant_field_not_global_gate': 'PASS',
            'normal_font_probe_hidden': T.footer(False, True) == T.SESSION,
        }
        with (out / 'followup_checks.json').open(
            'x', encoding='utf-8', newline='\n'
        ) as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
        self.vm.set_value('current', 'UniversalPP', '')
        self.vm.step = 3
        self.vm.calculate()
        self.render()
        assert 'Was fehlt' in self.vm.compact_display() and 1 in self.jump_buttons
        Clock.schedule_once(lambda dt: self.capture_indeterminate(out), 0.7)

    def capture_indeterminate(self, out):
        self.capture_view(out, 'indeterminate')
        before = (dict(self.vm.current), dict(self.vm.item_x), dict(self.vm.item_y))
        decision = dict(self.vm.last_result['engine'])
        self.toggle_clarification()
        assert self.vm.last_result['engine'] == decision
        self.jump_buttons[1].dispatch('on_release')
        assert self.vm.step == 1 and before == (
            self.vm.current,
            self.vm.item_x,
            self.vm.item_y,
        )
        with (out / 'indeterminate_checks.json').open(
            'x', encoding='utf-8', newline='\n'
        ) as stream:
            json.dump(
                {
                    'missing_first': True,
                    'jump_correct': True,
                    'values_preserved': True,
                    'toggle_no_verdict_change': True,
                },
                stream,
            )
        self.stop()


def run():
    ComparisonApp().run()
