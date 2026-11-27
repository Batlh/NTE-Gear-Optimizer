"""Thin Kivy bindings; no calculation formulas live in widgets."""

import os
import json
from pathlib import Path
from importlib.resources import files
from kivy.config import Config

from kivy.utils import platform as KIVY_PLATFORM
from .input_config import configure_input

configure_input(Config, KIVY_PLATFORM)
from .frame_policy import configure_frame_policy

FRAME_POLICY = configure_frame_policy(Config, KIVY_PLATFORM)
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
from .responsive_scroll import ResponsiveScrollView
from kivy.uix.modalview import ModalView
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.uix.image import Image
from .design_tokens import rgba, result_sections
from .design_widgets import (
    DesignButton,
    DesignTextInput,
    ResultCard,
    VerdictMark,
    StepSegments,
)
from kivy.uix.textinput import TextInput
from .viewmodel import ComparisonViewModel, numeric_hint, ark_level_hint
from . import texts as T
from .performance import timed

FONT = str(files('nte_gear_optimizer_app').joinpath('assets/DejaVuSans.ttf'))
BOLD_FONT = str(files('nte_gear_optimizer_app').joinpath('assets/DejaVuSans-Bold.ttf'))
LabelBase.register(name='NTEText', fn_regular=FONT, fn_bold=BOLD_FONT)


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
        self.active_debug = None
        self.debug = None
        self.keyboard_session = None
        self.keyboard_viewport = None
        self.active_touches = set()
        self.focus_scroll_event = None
        self.page_records = {}
        self.active_page = None
        self.building_page = None
        self.factory_counts = {}

    def factory_key(self, kind, explicit=None):
        if self.building_page is None:
            return None
        index = self.factory_counts.get(kind, 0)
        self.factory_counts[kind] = index + 1
        return (kind, explicit if explicit is not None else index)

    def label(self, text, size=16, *, cache_key=None, bold=False, color='text'):
        key = self.factory_key('label', cache_key)
        if key is not None and key in self.building_page['controls']:
            label = self.building_page['controls'][key]
            if label.text != text:
                label.text = text
            label.font_size = sp(size)
            label.bold = bold
            label.color = rgba(color)
            return label
        label = Label(
            text=text,
            font_name='NTEText',
            bold=bold,
            color=rgba(color),
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
        if key is not None:
            self.building_page['controls'][key] = label
        return label

    def button(self, text, callback, *, cache_key=None, role='outline'):
        key = self.factory_key('button', cache_key)
        if key is not None and key in self.building_page['controls']:
            button = self.building_page['controls'][key]
            button._nte_callback = callback
            button.role = role
            if button.text != text:
                button.text = text
            return button
        button = DesignButton(
            text=text,
            font_name='NTEText',
            font_size=sp(16),
            size_hint_y=None,
            height=dp(52),
            role=role,
        )
        button._nte_callback = callback

        def pressed(widget):
            widget._nte_action_touch = getattr(widget, '_nte_touch_id', None)
            if self.debug and widget._nte_action_touch is not None:
                self.debug.performance.feedback(
                    'button_pressed', widget._nte_action_touch
                )

        def released(widget):
            touch = getattr(widget, '_nte_action_touch', None)
            widget._nte_action_touch = None
            try:
                widget._nte_callback()
            finally:
                if self.debug and touch is not None:
                    self.debug.performance.action_response(touch)

        button.bind(on_press=pressed, on_release=released)
        if key is not None:
            self.building_page['controls'][key] = button
        return button

    @timed('selector_setup')
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
            displayed,
            lambda: self.open_selector(label, entries, callback),
            cache_key='selector:' + label,
        )
        self.selector_widgets[label] = widget
        self.body.add_widget(widget)

    @timed('selector_total', frame=True)
    def open_selector(self, title, entries, callback):
        build_token = (
            self.debug.performance.start(
                'selector_build', selector=title, step=self.vm.step + 1
            )
            if self.debug
            else None
        )
        self.dismiss_keyboard()
        if self.debug:
            self.debug.journal.emit(
                'selector_open', selector=title, current=self.selector_specs[title][1]
            )
        popup = ModalView(
            size_hint=(0.96, 0.90),
            auto_dismiss=False,
            background='',
            background_color=rgba('surface'),
        )
        layout = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(8))
        with layout.canvas.before:
            Color(*rgba('surface'))
            background = Rectangle(pos=layout.pos, size=layout.size)
        layout.bind(
            pos=lambda w, v: setattr(background, 'pos', v),
            size=lambda w, v: setattr(background, 'size', v),
        )
        layout.add_widget(self.label(title, 21))
        scroll = ResponsiveScrollView(do_scroll_x=False)
        rows = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(4))
        rows.bind(minimum_height=rows.setter('height'))
        self.selector_rows = []
        if self.debug:
            self.debug.scroll_observer.attach(scroll, 'selector:' + title)

        def select(value):
            if self.debug:
                current = self.selector_specs[title][1]
                self.debug.journal.emit(
                    'selection',
                    selector=title,
                    old_id=current,
                    new_id=value,
                    old_name=next(
                        (name for name, key in entries if key == current), None
                    ),
                    new_name=next(
                        (name for name, key in entries if key == value), None
                    ),
                )
            popup.dismiss(animation=False)
            self.active_selector = None
            callback(value)

        for name, value in entries:
            shown = ('✓  ' if value == self.selector_specs[title][1] else '') + name
            button = self.button(shown, lambda value=value: select(value))
            rows.add_widget(button)
            self.selector_rows.append((value, name, button))
        scroll.add_widget(rows)
        layout.add_widget(scroll)

        def cancel_selection():
            if self.debug:
                current = self.selector_specs[title][1]
                self.debug.journal.emit(
                    'selection_cancel',
                    selector=title,
                    old_id=current,
                    new_id=current,
                    name=next((name for name, key in entries if key == current), None),
                )
            popup.dismiss(animation=False)
            self.active_selector = None

        cancel = self.button('Abbrechen', cancel_selection)
        layout.add_widget(cancel)
        popup.add_widget(layout)
        self.active_selector = (title, popup, scroll, cancel)
        if self.debug:
            self.debug.performance.finish(build_token)
            open_token = self.debug.performance.start(
                'selector_open', selector=title, step=self.vm.step + 1
            )
            popup.bind(on_open=lambda *_: self.debug.performance.finish(open_token))
            popup.bind(
                on_dismiss=lambda *_: self.debug.performance.finish(
                    open_token, failed=True
                )
            )
        popup.open(animation=False)
        if self.debug:
            self.debug.trace.attach_tree(popup)

    def dismiss_keyboard(self):
        for widget in self.inputs.values():
            widget.focus = False
        if self.keyboard_session:
            self.keyboard_session.close()
        if self.keyboard_viewport:
            self.keyboard_viewport.reset()

    def observe_touch_lifetime(self, window, kind, touch):
        if kind == 'begin':
            self.active_touches.add(touch.uid)
        elif kind == 'update' and self.keyboard_viewport:
            self.keyboard_viewport.user_move()
        elif kind == 'end':
            self.active_touches.discard(touch.uid)
        return False

    def focus_scroll(self, widget, focused):
        if not focused:
            return
        if self.focus_scroll_event is not None:
            self.focus_scroll_event.cancel()

        def after_touch(dt):
            if not widget.focus or widget.parent is None:
                return
            if self.active_touches:
                self.focus_scroll_event = Clock.schedule_once(after_touch, 0.03)
                return
            # No animation: a cursor must not move under a short tap or while
            # the next text events are already arriving from the native IME.
            if KIVY_PLATFORM == 'android' and self.keyboard_viewport:
                self.keyboard_viewport.update()
            else:
                self.scroll.scroll_to(widget, padding=dp(24), animate=False)
            if self.debug:
                self.debug.journal.emit(
                    'focus_scroll_after_touch_end',
                    widget=self.debug.trace.describe(widget),
                )

        self.focus_scroll_event = Clock.schedule_once(after_touch, 0)

    def text_input(self, group, field, value):
        key = ('input', group, field)
        if self.building_page is not None and key in self.building_page['controls']:
            widget = self.building_page['controls'][key]
            self.inputs[(group, field)] = widget
            self.input_hints[(group, field)] = widget._nte_hint
            if widget.text != (value or ''):
                widget.text = value or ''
            return widget._nte_box
        widget = DesignTextInput(
            keyboard_mode='managed' if KIVY_PLATFORM == 'android' else 'auto',
            text=value or '',
            multiline=False,
            font_name='NTEText',
            font_size=sp(16),
            size_hint_y=None,
            height=dp(50),
            write_tab=False,
            # ScrollView can forward a short touch only after touch-up. Do not
            # let the global touch-up focus handler immediately close its IME.
            # Selection of another field and Done/navigation still dismiss it.
            unfocus_on_touch=False,
            input_type='number' if group == 'level' else 'text',
        )
        widget.bind(on_text_validate=lambda field: setattr(field, 'focus', False))
        if self.keyboard_session:
            widget.bind(focus=self.keyboard_session.focus_changed)
        widget.bind(focus=self.focus_scroll)
        if group == 'white':
            widget.bind(
                text=lambda _, value: setattr(self.vm, 'white_panel_base', value)
            )
        elif group == 'level':
            widget.bind(text=lambda _, value: setattr(self.vm, 'ark_level', value))
        else:
            widget.bind(text=lambda _, value: self.input_changed(group, field, value))
        self.inputs[(group, field)] = widget
        box = BoxLayout(
            orientation='vertical', size_hint_y=None, height=dp(50), pos_hint={'top': 1}
        )
        hint = Label(
            text='',
            font_name='NTEText',
            font_size=sp(14),
            halign='left',
            valign='middle',
            size_hint_y=None,
            height=0,
            color=rgba('warning_text'),
        )
        hint.bind(width=lambda _, width: setattr(hint, 'text_size', (width, None)))

        def resize(*_):
            hint.height = max(dp(32), hint.texture_size[1] + dp(8)) if hint.text else 0
            box.height = dp(50) + hint.height

        def validate(_, value):
            hint.text = (
                numeric_hint(value) if group != 'level' else ark_level_hint(value)
            )
            resize()

        hint.bind(texture_size=resize)
        widget.bind(text=validate)
        box.add_widget(widget)
        box.add_widget(hint)
        validate(widget, widget.text)
        self.input_hints[(group, field)] = hint
        widget._nte_box, widget._nte_hint = box, hint
        if self.building_page is not None:
            self.building_page['controls'][key] = widget
        return box

    def input_changed(self, group, field, value):
        self.vm.set_value(group, field, value)
        if field == 'ScalingPercentPP':
            self.update_white_visibility()

    def update_white_visibility(self):
        if self.white_box is None:
            return
        needed = self.vm.needs_white_base()
        if needed:
            self.white_box.height = max(dp(112), self.white_box.minimum_height)
            if self.white_box.parent is None:
                anchor = getattr(self, 'white_anchor', None)
                index = (
                    self.body.children.index(anchor) + 1
                    if anchor in self.body.children
                    else 0
                )
                self.body.add_widget(self.white_box, index=index)
                if self.debug:
                    self.debug.attach()
        elif self.white_box.parent is self.body:
            for key, widget in self.inputs.items():
                if key[0] == 'white':
                    widget.focus = False
            self.body.remove_widget(self.white_box)

    def build(self):
        Window.softinput_mode = 'below_target'
        Window.clearcolor = rgba('background')
        self.root_box = BoxLayout(orientation='vertical', padding=dp(16), spacing=dp(8))
        from .debug_control import DebugControl

        self.debug = DebugControl(self)
        self.debug.journal.emit('frame_policy', **FRAME_POLICY)
        if KIVY_PLATFORM == 'android':
            from .frame_policy import request_android_mode

            request_android_mode(self.debug.journal.emit)
        if KIVY_PLATFORM == 'android':
            from .keyboard_session import KeyboardSession

            self.keyboard_session = KeyboardSession(
                Window, Clock, self.debug.journal.emit
            )
        Window.bind(on_motion=self.observe_touch_lifetime)
        header = BoxLayout(spacing=dp(12), size_hint_y=None, height=dp(64))
        header.add_widget(
            Image(
                source=str(
                    files('nte_gear_optimizer_app').joinpath(
                        'assets/icons/kiwi_slice_transparent_512.png'
                    )
                ),
                size_hint=(None, 1),
                width=dp(36),
            )
        )
        titles = BoxLayout(orientation='vertical')
        title = self.label(T.TITLE, 22, bold=True)
        title.text_size = (None, None)
        title.shorten = True
        title.shorten_from = 'right'
        title.height = dp(30)
        title.bind(width=lambda w, v: setattr(w, 'text_size', (v, dp(30))))
        titles.add_widget(title)
        subtitle = self.label(T.SUBTITLE, 14, color='muted')
        subtitle.height = dp(32)
        titles.add_widget(subtitle)
        header.add_widget(titles)
        self.root_box.add_widget(header)
        self.segments = StepSegments()
        self.root_box.add_widget(self.segments)
        self.progress = self.label('', 17, bold=True)
        self.root_box.add_widget(self.progress)
        self.scroll = ResponsiveScrollView(do_scroll_x=False)
        self.body = BoxLayout(orientation='vertical', spacing=dp(10), size_hint_y=None)
        self.body.bind(minimum_height=self.body.setter('height'))
        self.scroll.add_widget(self.body)
        self.root_box.add_widget(self.scroll)
        footer = BoxLayout(spacing=dp(12), size_hint_y=None, height=dp(54))
        self.back_button = self.button(T.BACK, self.go_back)
        self.next_button = self.button(T.NEXT, self.go_next, role='primary')
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
        self.debug_button = self.button('Debug', self.debug.menu, role='text')
        self.debug_button.height = dp(48)
        self.root_box.add_widget(self.debug_button)
        self.render()
        if KIVY_PLATFORM == 'android':
            from .minimal_keyboard_viewport import (
                MinimalKeyboardViewport,
                android_geometry_reader,
            )

            self.keyboard_viewport = MinimalKeyboardViewport(
                self,
                Window,
                Clock,
                android_geometry_reader(),
                self.debug.journal.emit,
                gap=dp(8),
            )
        return self.root_box

    def go_back(self):
        self.dismiss_keyboard()
        before = self.vm.step
        self.vm.back()
        if self.debug:
            self.debug.journal.flush_inputs(force=True)
            self.debug.journal.emit(
                'step', action='back', before=before, after=self.vm.step
            )
        self.render()

    def go_next(self):
        self.dismiss_keyboard()
        before = self.vm.step
        self.vm.next()
        if self.debug:
            self.debug.journal.flush_inputs(force=True)
            self.debug.journal.emit(
                'step', action='next', before=before, after=self.vm.step
            )
        if self.vm.step == 3:
            self.vm.calculate()
            if self.debug:
                self.debug.result()
        self.render()

    def change(self, method, value):
        method(value)
        self.render()

    def profile_change(self, key, value):
        self.vm.set_override(key, value)
        self.render()

    PAGE_FIELDS = (
        'inputs',
        'input_hints',
        'white_box',
        'white_anchor',
        'zero_buttons',
        'selector_specs',
        'selector_widgets',
        'jump_buttons',
    )

    def page_key(self):
        if self.vm.step in (1, 2):
            groups = tuple(
                (k, tuple(v)) for k, v in self.vm.groups(self.vm.step == 2).items()
            )
            return (self.vm.step, groups, self.vm.profile().get('ScalingStat'))
        return (self.vm.step,)

    def page_signature(self):
        if self.vm.step == 0:
            return (
                self.vm.character_id,
                self.vm.ark_id,
                self.vm.profile_id,
                self.vm.branch_id,
                tuple(sorted(self.vm.overrides.items())),
            )
        if self.vm.step == 3:
            return (
                id(self.vm.last_result),
                self.details_expanded,
                self.clarification_expanded,
                self.show_all_values,
            )
        return self.page_key()

    def sync_input_values(self, fields=None):
        groups = {
            'current': self.vm.current,
            'x': self.vm.item_x,
            'y': self.vm.item_y,
            'level': {'ArkLevel': self.vm.ark_level},
            'white': {'WhitePanelBase': self.vm.white_panel_base},
        }
        for (group, field), widget in self.inputs.items():
            if fields is not None and (group, field) not in fields:
                continue
            value = groups[group].get(field) or ''
            if widget.text != value:
                widget.text = value
        self.update_white_visibility()

    @timed('render', frame=True)
    def render(self):
        from .reconcile_layout import ReconcileLayout

        self.vm.performance = self.debug.performance if self.debug else None
        self.dismiss_keyboard()
        if self.active_page is not None:
            self.active_page['state'] = {
                name: getattr(self, name, None) for name in self.PAGE_FIELDS
            }
            self.active_page['scroll_y'] = self.scroll.scroll_y
        key = self.page_key()
        page = self.page_records.get(key)
        if page is None:
            body = (ReconcileLayout if self.vm.step in (0, 3) else BoxLayout)(
                orientation='vertical', spacing=dp(10), size_hint_y=None
            )
            body.bind(minimum_height=body.setter('height'))
            page = {
                'body': body,
                'controls': {},
                'state': {},
                'signature': None,
                'scroll_y': 1,
            }
            self.page_records[key] = page
            # Bound retained schema variants. Four ordinary pages always fit;
            # old profile-specific variants may be rebuilt after many changes.
            if len(self.page_records) > 10:
                victim = next(
                    k for k in self.page_records if k != key and k[0] in (1, 2)
                )
                self.page_records.pop(victim)
        if self.body is not page['body']:
            if self.body.parent is self.scroll:
                self.scroll.remove_widget(self.body)
            self.body = page['body']
            self.scroll.add_widget(self.body)
        self.active_page = page
        defaults = {
            'inputs': {},
            'input_hints': {},
            'white_box': None,
            'white_anchor': None,
            'zero_buttons': [],
            'selector_specs': {},
            'selector_widgets': {},
            'jump_buttons': {},
        }
        for name, value in defaults.items():
            setattr(self, name, page['state'].get(name, value))
        self.progress.text = (
            'Aktuelles Teil ↔ Neues Teil'
            if self.vm.step == 2
            else T.STEPS[self.vm.step]
        )
        self.segments.step = self.vm.step
        self.back_button.disabled = self.vm.step == 0
        self.next_button.text = T.NEXT if self.vm.step < 3 else T.UI['recalculate']
        signature = self.page_signature()
        refresh = page['signature'] != signature
        if refresh:
            if self.vm.step in (0, 3):
                self.building_page = page
                self.factory_counts = {}
                self.body.begin_refresh()
                self.inputs = {}
                self.input_hints = {}
                self.selector_specs = {}
                self.selector_widgets = {}
                self.jump_buttons = {}
            self.populate_page()
            if self.vm.step in (0, 3):
                self.body.end_refresh()
            self.building_page = None
            page['signature'] = signature
            if self.vm.step == 3:
                page['result_reference'] = self.vm.last_result
            page['state'] = {
                name: getattr(self, name, None) for name in self.PAGE_FIELDS
            }
        self.sync_input_values()
        self.scroll.scroll_y = page['scroll_y']
        if self.debug:
            self.debug.attach()
            self.debug.journal.emit(
                'screen', step=self.vm.step, retained_page=not refresh
            )

    def populate_page(self):
        if self.vm.step == 0:
            self.selection()
        elif self.vm.step in (1, 2):
            self.values_screen(parts=self.vm.step == 2)
        else:
            self.result_screen()

    def result_card(self, key):
        cache = self.factory_key('card', key)
        card = self.building_page['controls'].get(cache)
        if card is None:
            card = ResultCard()
            self.building_page['controls'][cache] = card
        card.begin_refresh()
        self.body.add_widget(card)
        return card

    def result_screen(self):
        leading, changed, guide, hints = result_sections(
            self.vm.compact_display(), T.CHANGED, T.HINTS
        )
        engine = self.vm.last_result['engine']
        top = self.result_card('verdict')
        cache = self.factory_key('verdict_mark', 'result')
        mark = self.building_page['controls'].get(cache)
        if mark is None:
            mark = VerdictMark()
            self.building_page['controls'][cache] = mark
        mark.verdict = engine.get('Verdict') or ''
        from .reconcile_layout import ReconcileLayout

        row_key = self.factory_key('result_header', 'verdict')
        row = self.building_page['controls'].get(row_key)
        if row is None:
            row = ReconcileLayout(
                orientation='horizontal', size_hint_y=None, height=dp(48), spacing=dp(8)
            )
            self.building_page['controls'][row_key] = row
        row.begin_refresh()
        row.add_widget(mark)
        top.add_widget(row)
        head = leading.split('\n\nWas fehlt', 1)[0]
        title, _, rest = head.partition('\n')
        color = (
            'accent_text'
            if engine.get('Verdict') == 'BETTER'
            else ('warning_text' if engine.get('Verdict') == 'WORSE' else 'text')
        )
        row.add_widget(
            self.label(
                T.VERDICTS.get(engine.get('Verdict'), 'Unentscheidbar'),
                22,
                bold=True,
                color=color,
                cache_key='verdict:title',
            )
        )
        row.end_refresh()
        if rest:
            top.add_widget(self.label(rest, 14, cache_key='verdict:rest'))
        top.end_refresh()
        if engine.get('Verdict') is None:
            missing = self.result_card('missing')
            missing.add_widget(
                self.label('Was fehlt', 17, bold=True, cache_key='missing:title')
            )
            for step, messages in self.vm.missing_groups():
                missing.add_widget(
                    self.label(
                        T.STEPS[step], 17, bold=True, cache_key=f'missing:{step}:title'
                    )
                )
                button = self.button(
                    'Zu Schritt ' + str(step + 1),
                    lambda step=step: self.jump_to(step),
                    cache_key=f'missing:{step}:jump',
                )
                self.jump_buttons[step] = button
                missing.add_widget(button)
                missing.add_widget(
                    self.label(
                        '\n'.join(messages),
                        color='warning_text',
                        cache_key=f'missing:{step}:body',
                    )
                )
            missing.end_refresh()
        changes = self.result_card('changes')
        changes.add_widget(
            self.label('Was sich ändert', 17, bold=True, cache_key='changes:title')
        )
        changes.add_widget(
            self.label(
                changed.removeprefix(T.CHANGED).lstrip('\n'), cache_key='changes:body'
            )
        )
        if engine.get('Verdict') is None:
            changes.add_widget(
                self.button(
                    'Alle Werte zur Klärung'
                    if not self.clarification_expanded
                    else 'Klärungswerte einklappen',
                    self.toggle_clarification,
                    cache_key='clarification',
                )
            )
            if self.clarification_expanded:
                changes.add_widget(
                    self.label(
                        self.vm.clarification_display(), cache_key='clarification:body'
                    )
                )
        changes.end_refresh()
        guide_card = self.result_card('guide')
        guide_card.add_widget(
            self.label('Guide', 17, bold=True, cache_key='guide:title')
        )
        if guide:
            badge = self.label(
                'für 1.5 ungeprüft' if T.GUIDE_WARNING in guide else 'Richtwert',
                14,
                color='warning_text',
                cache_key='guide:badge',
            )
            if not hasattr(badge, '_nte_status_background'):
                with badge.canvas.before:
                    Color(*rgba('warning_surface'))
                    badge._nte_status_background = RoundedRectangle(
                        pos=badge.pos, size=badge.size, radius=[dp(10)]
                    )
                badge.bind(
                    pos=lambda w, v: setattr(w._nte_status_background, 'pos', v),
                    size=lambda w, v: setattr(w._nte_status_background, 'size', v),
                )
            guide_card.add_widget(badge)
        guide_card.add_widget(
            self.label(
                guide or T.NO_GUIDE,
                14,
                color='warning_text' if guide else 'muted',
                cache_key='guide:body',
            )
        )
        guide_card.end_refresh()
        notes = self.result_card('hints')
        notes.add_widget(self.label(T.HINTS, 17, bold=True, cache_key='hints:title'))
        notes.add_widget(self.label(hints, cache_key='hints:body'))
        notes.end_refresh()
        details = self.result_card('details')
        self.details_button = self.button(
            T.DETAILS_CLOSE if self.details_expanded else T.DETAILS_OPEN,
            self.toggle_details,
            cache_key='details:toggle',
        )
        details.add_widget(self.details_button)
        if self.details_expanded:
            self.all_values_button = self.button(
                T.SHOW_CHANGED if self.show_all_values else T.SHOW_ALL,
                self.toggle_all_values,
                cache_key='details:all',
            )
            details.add_widget(self.all_values_button)
            details.add_widget(
                self.label(
                    self.vm.details_display(self.show_all_values),
                    cache_key='details:body',
                )
            )
        details.end_refresh()

    def jump_to(self, step):
        before = self.vm.step
        self.vm.jump_to(step)
        if self.debug:
            self.debug.journal.emit('step', action='jump', before=before, after=step)
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

    @timed('zero', frame=True)
    def zero(self, name, parts):
        self.vm.zero_group(name, parts)
        targets = ('x', 'y') if parts else ('current',)
        fields = {
            (group, field) for group in targets for field in self.vm.groups(parts)[name]
        }
        self.sync_input_values(fields)
        if self.debug:
            self.debug.journal.emit('zero_bonus', group=name, parts=parts)

    def values_screen(self, parts=False):
        self.body.add_widget(self.label(T.SWAP_NOTE if parts else T.CURRENT_NOTE))
        for name, fields in self.vm.groups(parts).items():
            self.body.add_widget(self.label(T.GROUP_NAMES[name], 17, bold=True))
            if parts or name != 'scale':
                zero = self.button(
                    T.ZERO, lambda name=name: self.zero(name, parts), role='pill'
                )
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
        if not self.vm.fields():
            self.body.add_widget(self.label(T.UI['missing_profile']))
        if parts:
            self.white_anchor = self.label(T.UI['parts_hint'])
            self.body.add_widget(self.white_anchor)
            self.update_white_visibility()

    def on_pause(self):
        self.dismiss_keyboard()
        self.active_touches.clear()
        if self.debug:
            self.debug.journal.flush_inputs(force=True)
            self.debug.journal.emit('app_pause')
        return True

    def on_resume(self):
        if self.debug:
            self.debug.journal.emit('app_resume')

    def on_stop(self):
        if self.keyboard_viewport:
            self.keyboard_viewport.stop()
        self.dismiss_keyboard()
        if self.debug:
            self.debug.stop()

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
