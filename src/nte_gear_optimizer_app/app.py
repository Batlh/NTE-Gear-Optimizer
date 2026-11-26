"""Thin Kivy bindings; no calculation formulas live in widgets."""

import os
import json
from pathlib import Path
from importlib.resources import files
from kivy.config import Config

Config.set('input', 'mouse', 'mouse,multitouch_on_demand')
Config.set('kivy', 'exit_on_escape', '0')
from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner, SpinnerOption
from kivy.uix.textinput import TextInput
from .viewmodel import ComparisonViewModel
from . import texts as T

FONT = str(files('nte_gear_optimizer_app').joinpath('assets/Roboto-Regular.ttf'))
LabelBase.register(name='NTEText', fn_regular=FONT, fn_bold=FONT)


class ComparisonApp(App):
    title = T.TITLE

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.vm = ComparisonViewModel()
        self.inputs = {}
        self.zero_buttons = []
        self.smoke_index = 0

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
        option = type(
            'NTEOption',
            (SpinnerOption,),
            {'height': dp(52), 'font_name': 'NTEText', 'font_size': sp(17)},
        )
        widget = Spinner(
            text=displayed,
            values=tuple(mapping),
            option_cls=option,
            font_name='NTEText',
            font_size=sp(17),
            size_hint_y=None,
            height=dp(52),
        )
        widget.bind(
            text=lambda _, text: callback(mapping[text]) if text in mapping else None
        )
        self.body.add_widget(widget)

    def text_input(self, group, field, value):
        widget = TextInput(
            text=value or '',
            multiline=False,
            font_name='NTEText',
            font_size=sp(18),
            size_hint_y=None,
            height=dp(50),
            write_tab=False,
        )
        if group == 'white':
            widget.bind(
                text=lambda _, value: setattr(self.vm, 'white_panel_base', value)
            )
        elif group == 'level':
            widget.bind(text=lambda _, value: setattr(self.vm, 'ark_level', value))
        else:
            widget.bind(text=lambda _, value: self.vm.set_value(group, field, value))
        self.inputs[(group, field)] = widget
        return widget

    def build(self):
        Window.clearcolor = (0.065, 0.085, 0.11, 1)
        self.root_box = BoxLayout(orientation='vertical', padding=dp(16), spacing=dp(8))
        self.root_box.add_widget(self.label(T.LOGO + '   ' + T.TITLE, 23))
        self.root_box.add_widget(self.label(T.SUBTITLE, 14))
        self.progress = self.label('', 20)
        self.root_box.add_widget(self.progress)
        self.scroll = ScrollView(do_scroll_x=False)
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
                T.FONT_PROBE
                if os.environ.get('NTE_TEST_MODE') == 'smoke'
                else T.SESSION,
                14,
            )
        )
        self.render()
        return self.root_box

    def go_back(self):
        self.vm.back()
        self.render()

    def go_next(self):
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
        self.body.clear_widgets()
        self.inputs = {}
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
            self.body.add_widget(self.label(self.vm.display()))

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
                    + str(r.get('ProfileType') or 'unbekannt'),
                )
                for r in self.vm.branches()
            ]
            self.spinner(
                T.UI['branch'],
                options,
                self.vm.branch_id,
                lambda value: self.change(self.vm.choose_branch, value),
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
            self.body.add_widget(self.label(name, 21))
            if parts or name != 'Skalierung':
                zero = self.button(T.ZERO, lambda name=name: self.zero(name, parts))
                self.zero_buttons.append(zero)
                self.body.add_widget(zero)
            for field in fields:
                self.body.add_widget(self.label(T.FIELD_LABELS[field]))
                row = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(52))
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
            self.body.add_widget(self.label(T.FIELD_LABELS['WhitePanelBase']))
            self.body.add_widget(
                self.text_input('white', 'WhitePanelBase', self.vm.white_panel_base)
            )
        if not self.vm.fields():
            self.body.add_widget(self.label(T.UI['missing_profile']))
        if parts:
            self.body.add_widget(self.label(T.UI['parts_hint']))

    def on_start(self):
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

    def capture_and_advance(self, out):
        Window.screenshot(
            name=str(out / ('step_' + str(self.smoke_index + 1) + '.png'))
        )
        if self.smoke_index == 3:
            Clock.schedule_once(lambda dt: self.stop(), 0.4)
            return
        self.next_button.trigger_action(duration=0)
        self.smoke_index += 1
        Clock.schedule_once(self.smoke, 0.7)


def run():
    ComparisonApp().run()
