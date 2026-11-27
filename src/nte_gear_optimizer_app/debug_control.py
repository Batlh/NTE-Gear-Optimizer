"""Kivy adapter for the offline journal and explicit report-export menu."""

import weakref

from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.core.text import Label as CoreLabel
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, InstructionGroup, Rectangle
from kivy.metrics import Metrics, dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.modalview import ModalView
from kivy.base import ExceptionHandler, ExceptionManager
from kivy.utils import platform

from .debug_journal import (
    DebugJournal,
    PRIVACY_NOTICE,
    install_uncaught_hooks,
    private_log_directory,
)
from .debug_export import (
    android_download,
    android_share,
    build_metadata,
    desktop_report,
)
from .diagnostic_trace import InputTrace
from .performance import PerformanceTrace, timed
from .viewmodel import ark_level_hint, normalize, numeric_hint


class DebugControl:
    def __init__(self, app):
        self.app = app
        android_files = None
        if platform == 'android':
            from jnius import autoclass

            self.activity = autoclass('org.kivy.android.PythonActivity').mActivity
            android_files = str(self.activity.getFilesDir().getAbsolutePath())
        self.journal = DebugJournal(private_log_directory(platform, android_files))
        self.performance = PerformanceTrace(self.journal.emit)
        Window.bind(on_flip=self.performance.frame)
        self.metadata = build_metadata()
        self.bound = weakref.WeakSet()
        self.overlay = False
        self.overlay_canvas = InstructionGroup()
        Window.canvas.after.add(self.overlay_canvas)
        self.last_touch = None
        self.last_consumer = ''
        self.consumer_depth = -1
        self.native_state = None
        self.trace = InputTrace(app, self.observe)
        self.trace.attach_window(Window)
        install_uncaught_hooks(self.journal)
        journal = self.journal

        class JournalExceptionHandler(ExceptionHandler):
            def handle_exception(self, error):
                journal.exception(error, caught=False)
                return ExceptionManager.RAISE

        self.exception_handler = JournalExceptionHandler()
        ExceptionManager.add_handler(self.exception_handler)
        Clock.schedule_interval(lambda dt: self.journal.flush_inputs(), 0.1)
        self.scroll_event = Clock.create_trigger(self.scroll_record, 0.2)
        self.journal.emit('app_start', device=self.device())
        if platform == 'android':
            Clock.schedule_interval(self.native_keyboard_state, 0.1)

    def device(self):
        values = {
            'app_version': '0.29.0 Phase 2A-3 (Test)',
            'commit': self.metadata.get('commit', 'development-unbundled'),
            'version_code': None,
            'platform': platform,
            'screen': list(Window.size),
            'density': Metrics.density,
        }
        if platform == 'android':
            try:
                from jnius import autoclass

                values['android_version'] = str(
                    autoclass('android.os.Build$VERSION').RELEASE
                )
                values['model'] = str(autoclass('android.os.Build').MODEL)
                package = self.activity.getPackageManager().getPackageInfo(
                    self.activity.getPackageName(), 0
                )
                values['version_code'] = int(package.versionCode)
                values['ime'] = str(
                    autoclass('android.provider.Settings$Secure').getString(
                        self.activity.getContentResolver(), 'default_input_method'
                    )
                )
            except Exception as error:
                self.journal.exception(error, caught=True)
        return values

    def observe(self, row):
        data = dict(row)
        event = data.pop('event')
        data['trace_seq'] = data.pop('seq')
        data['trace_ms'] = data.pop('ms')
        self.journal.emit(event, **data)
        if event == 'focus' and row['focused']:
            self.performance.response('focus')
        if event == 'touch_accepted' and row['widget']['class'] == 'Button':
            self.performance.response('button_pressed', row['touch_id'])
        if event == 'focus' and not row['focused']:
            self.journal.flush_inputs(row['widget'].get('field'), force=True)
        if event == 'motion_begin':
            self.performance.touch_begin(row['touch_id'])
            self.consumer_depth = -1
            self.last_touch = [
                row['normalized'][0] * Window.width,
                row['normalized'][1] * Window.height,
            ]
        if (
            event == 'touch_accepted'
            and row['widget'].get('depth', 0) > self.consumer_depth
        ):
            self.consumer_depth = row['widget'].get('depth', 0)
            w = row['widget']
            self.last_consumer = w.get('field') or w.get('label') or w['class']
            self.last_consumer += (
                f' · sichtbar={w.get("tree_visible")} · aktiv={w.get("enabled")}'
            )
        if self.overlay:
            self.draw_overlay()

    def native_keyboard_state(self, dt):
        try:
            from jnius import autoclass

            decor = self.activity.getWindow().getDecorView()
            rect = autoclass('android.graphics.Rect')()
            decor.getWindowVisibleDisplayFrame(rect)
            position = [0, 0]
            decor.getLocationOnScreen(position)
            status = {
                'frame': [rect.left, rect.top, rect.right, rect.bottom],
                'decor_origin': position,
                'ime_visible': None,
                'ime_height': None,
            }
            if autoclass('android.os.Build$VERSION').SDK_INT >= 30:
                insets = decor.getRootWindowInsets()
                if insets is not None:
                    kind = autoclass('android.view.WindowInsets$Type').ime()
                    status['ime_visible'] = bool(insets.isVisible(kind))
                    status['ime_height'] = insets.getInsets(kind).bottom
            if status != self.native_state:
                self.native_state = status
                self.journal.emit('native_keyboard_window', **status)
        except Exception as error:
            if self.native_state != 'unavailable':
                self.journal.exception(error, caught=True)
                self.native_state = 'unavailable'

    def draw_overlay(self):
        self.overlay_canvas.clear()
        if not self.overlay:
            return
        if self.last_touch:
            self.overlay_canvas.add(Color(1, 0.35, 0.1, 0.85))
            self.overlay_canvas.add(
                Ellipse(
                    pos=(self.last_touch[0] - dp(7), self.last_touch[1] - dp(7)),
                    size=(dp(14), dp(14)),
                )
            )
        text = CoreLabel(
            text=self.last_consumer or 'Touch-Diagnose aktiv',
            font_name='NTEText',
            font_size=dp(12),
            text_size=(Window.width - dp(16), None),
        )
        text.refresh()
        self.overlay_canvas.add(Color(0.03, 0.04, 0.06, 0.92))
        self.overlay_canvas.add(
            Rectangle(
                pos=(dp(4), Window.height - text.texture.height - dp(8)),
                size=text.texture.size,
            )
        )
        self.overlay_canvas.add(Color(1, 1, 1, 1))
        self.overlay_canvas.add(
            Rectangle(
                pos=(dp(4), Window.height - text.texture.height - dp(8)),
                texture=text.texture,
                size=text.texture.size,
            )
        )

    def field_record(self, key, value):
        group, field = key
        hint = ark_level_hint(value) if group == 'level' else numeric_hint(value)
        try:
            normalized = (
                (str(int(value.strip())) if value.strip() and not hint else None)
                if group == 'level'
                else normalize(value)
            )
        except ValueError, TypeError:
            normalized = None
        return {
            'group': group,
            'field': field,
            'raw': value,
            'normalized': normalized,
            'hint': hint,
            'accepted': not hint or normalized is not None,
        }

    def attach(self):
        self.trace.attach_tree(self.app.root_box)
        for key, widget in self.app.inputs.items():
            if widget in self.bound:
                continue
            self.bound.add(widget)

            def changed(w, value, key=key):
                row = self.field_record(key, value)
                self.journal.input(':'.join(key), value, row['normalized'], row['hint'])

            widget.bind(text=changed)
        scroll = self.app.scroll
        if scroll not in self.bound:
            self.bound.add(scroll)
            scroll.bind(scroll_y=lambda *_: self.scroll_event())

    def scroll_record(self, dt):
        self.journal.emit(
            'scroll', step=self.app.vm.step, scroll_y=self.app.scroll.scroll_y
        )

    def state(self):
        vm = self.app.vm
        raws = [
            *((('current', k), v) for k, v in vm.current.items()),
            *((('x', k), v) for k, v in vm.item_x.items()),
            *((('y', k), v) for k, v in vm.item_y.items()),
            (('level', 'ArkLevel'), vm.ark_level),
            (('white', 'WhitePanelBase'), vm.white_panel_base),
        ]
        raw_map = dict(raws)
        raw_map.update({key: widget.text for key, widget in self.app.inputs.items()})
        raws = list(raw_map.items())
        return {
            'timing_in_progress': self.performance.in_progress(),
            'step': vm.step,
            'character_id': vm.character_id,
            'ark_id': vm.ark_id,
            'profile_id': vm.profile_id,
            'branch_id': vm.branch_id,
            'overrides': dict(vm.overrides),
            'inputs': [self.field_record(k, v) for k, v in raws],
            'result': vm.last_result,
            'focused_fields': [
                ':'.join(k) for k, w in self.app.inputs.items() if w.focus
            ],
        }

    def result(self):
        self.journal.flush_inputs(force=True)
        self.journal.emit(
            'result',
            result=self.app.vm.last_result,
            missing=self.app.vm.missing_groups(),
        )

    def popup(self, title, actions):
        self.app.dismiss_keyboard()
        popup = ModalView(size_hint=(0.95, 0.88), auto_dismiss=False)
        layout = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(8))
        layout.add_widget(self.app.label(title))
        buttons = {}
        for label, action in actions:

            def selected(action=action):
                popup.dismiss()
                self.app.active_debug = None
                try:
                    action()
                except Exception as error:
                    self.journal.exception(error, caught=True)
                    self.popup(
                        'Fehler protokolliert – bitte Zwischenablage oder Teilen versuchen.',
                        [('Zurück', self.menu)],
                    )

            button = self.app.button(label, selected)
            buttons[label] = button
            layout.add_widget(button)
        popup.add_widget(layout)
        self.app.active_debug = (popup, buttons)
        popup.open()
        self.trace.attach_tree(popup)
        return popup

    def menu(self):
        self.journal.emit('debug_menu_open')
        actions = [
            ('Debug-Bericht exportieren', lambda: self.confirm_export('share')),
            ('In Zwischenablage kopieren', lambda: self.confirm_export('clipboard')),
            (
                'Touch-Diagnose aus' if self.overlay else 'Touch-Diagnose an',
                self.toggle_overlay,
            ),
            ('Protokoll leeren', self.confirm_clear),
        ]
        if platform == 'android':
            actions.insert(
                1, ('In Downloads speichern', lambda: self.confirm_export('downloads'))
            )
        actions.append(('Schließen', lambda: None))
        self.popup('Debug – nur auf diesem Gerät', actions)

    def toggle_overlay(self):
        self.overlay = not self.overlay
        self.journal.emit('touch_overlay', enabled=self.overlay)
        self.draw_overlay()

    def confirm_clear(self):
        self.popup(
            'Lokales Ablaufprotokoll wirklich leeren?',
            [
                ('Ja, Protokoll leeren', lambda: self.journal.clear(confirmed=True)),
                ('Abbrechen', self.menu),
            ],
        )

    def confirm_export(self, mode):
        self.popup(
            PRIVACY_NOTICE,
            [('Fortfahren', lambda: self.export(mode)), ('Abbrechen', self.menu)],
        )

    @timed('export')
    def export(self, mode):
        self.journal.emit('report_export_requested', mode=mode)
        report = self.journal.report(self.device(), self.state())
        filename = self.journal.filename()
        if mode == 'clipboard':
            Clipboard.copy(report)
            destination = 'In Zwischenablage kopiert.'
        elif platform == 'android':
            destination = (
                android_download(report, filename)
                if mode == 'downloads'
                else android_share(report, filename)
            )
        else:
            destination = desktop_report(report, filename)
        # The destination path is displayed, never copied into journal entries.
        self.journal.emit('report_export_complete', mode=mode, filename=filename)
        if platform != 'android' or mode != 'share':
            self.popup(destination, [('Schließen', lambda: None)])

    def test_exception(self):
        if not self.metadata.get('emulator_test_only') and not __import__(
            'os'
        ).environ.get('NTE_TEST_MODE'):
            raise RuntimeError('Test exception is available only in isolated test mode')
        try:
            raise RuntimeError('NTE_A3_TEST_EXCEPTION – nur Testmodus')
        except RuntimeError as error:
            self.journal.exception(error, caught=True)

    def stop(self):
        Window.unbind(on_flip=self.performance.frame)
        self.journal.flush_inputs(force=True)
        self.journal.emit('app_stop')
        ExceptionManager.remove_handler(self.exception_handler)
