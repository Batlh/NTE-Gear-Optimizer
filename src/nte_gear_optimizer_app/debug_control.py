"""Kivy adapter for the offline journal and explicit report-export menu."""

import weakref
from concurrent.futures import ThreadPoolExecutor

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
    PRIVACY_NOTICE,
    install_uncaught_hooks,
    private_log_directory,
)
from .background_journal import BackgroundJournal
from .frame_profile import FrameProfiler, phase
from .design_tokens import rgba
from .debug_export import (
    android_download,
    android_share,
    android_share_context,
    build_metadata,
    desktop_report,
)
from .diagnostic_trace import InputTrace
from .performance import PerformanceTrace
from .viewmodel import ark_level_hint, normalize, numeric_hint


class DebugControl:
    def __init__(self, app):
        self.app = app
        android_files = None
        if platform == 'android':
            from jnius import autoclass

            self.activity = autoclass('org.kivy.android.PythonActivity').mActivity
            android_files = str(self.activity.getFilesDir().getAbsolutePath())
        self.journal = BackgroundJournal(private_log_directory(platform, android_files))
        self.performance = PerformanceTrace(self.journal.emit)
        Window.bind(on_flip=self.performance.frame)
        from .scroll_observer import ScrollObserver

        from .touch_slop import touch_slop_policy

        self.scroll_observer = ScrollObserver(
            Window,
            Clock,
            platform,
            self.journal.emit,
            touch_slop=touch_slop_policy()['window_px'],
        )
        from .touch_slop import TouchIntentObserver

        self.touch_intent = TouchIntentObserver(Window, self.journal.emit)
        self.frame_profiler = FrameProfiler(
            Window,
            lambda: (
                self.scroll_observer.metrics.current is not None
                and self.scroll_observer.metrics.current.get('slop_crossed') is not None
            ),
        )
        from kivy.base import EventLoop
        from .frame_runtime_hooks import RuntimeHooks

        self.frame_profiler.runtime_hooks = RuntimeHooks(
            self.frame_profiler, Clock, EventLoop, CoreLabel
        )
        from .gesture_gc import GestureGCPolicy

        self.gc_policy = GestureGCPolicy(
            lambda: (
                self.scroll_observer.metrics.current is not None
                or bool(self.app.active_touches)
            )
        )
        self.frame_profiler.gc_policy = self.gc_policy
        self.scroll_observer.gc_policy = self.gc_policy
        self.scroll_observer.metrics.profile = self.frame_profiler
        self.metadata = build_metadata()
        self.bound = weakref.WeakSet()
        self.full_report = False
        self.export_pool = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix='NTE-report-export'
        )
        self.export_future = None
        self.stopped = False
        self.overlay = False
        self.overlay_canvas = InstructionGroup()
        Window.canvas.after.add(self.overlay_canvas)
        self.last_touch = None
        self.last_consumer = ''
        from .touch_routes import TouchRoutes

        self.routes = TouchRoutes()
        self.display_touch_id = None
        self.last_chain = ''
        self.overlay_event = Clock.create_trigger(lambda dt: self.draw_overlay(), 0)
        self.native_state = None
        self.skip_closed_keyboard_poll_on_scroll = True
        self.keyboard_probe_skips = 0
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
        self.defer_input_flush_on_scroll = (
            False  # Trial: activate only after measured benefit.
        )
        self.input_flush_skips = 0
        Clock.schedule_interval(self.flush_idle_inputs, 0.1)
        self.journal.emit('app_start', device=self.device())
        if platform == 'android':
            Clock.schedule_interval(self.native_keyboard_state, 0.1)

    def flush_idle_inputs(self, dt=0):
        gesture = self.scroll_observer.metrics.current
        if (
            self.defer_input_flush_on_scroll
            and gesture is not None
            and gesture.get('slop_crossed') is not None
        ):
            self.input_flush_skips += 1
            return  # None keeps the recurring callback scheduled.
        self.journal.flush_inputs()

    def device(self):
        values = {
            'app_version': '0.29.0 Phase 2A-6 (Profil-Test)',
            'commit': self.metadata.get('commit', 'development-unbundled'),
            'version_code': None,
            'platform': platform,
            'screen': list(Window.size),
            'density': Metrics.density,
            'effective_clock_maxfps': Clock._max_fps,
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

    def finish_route(self, identifier):
        route = self.routes.snapshot(identifier)
        if route is None:
            return
        self.journal.emit('touch_route_final', **route)
        self.refresh_route(identifier)

    def refresh_route(self, identifier):
        if str(identifier) != self.display_touch_id:
            return
        route = self.routes.snapshot(identifier)
        if not route or not route['target']:
            return
        w = route['target']
        self.last_consumer = (
            w['class'] + ' ' + str(w.get('field') or w.get('label') or '')
        )
        self.last_consumer += (
            f' · sichtbar={w.get("tree_visible")} · aktiv={w.get("enabled")}'
        )
        chain = []
        for node in route['chain']:
            name = node.get('class', '?')
            if not chain or chain[-1] != name:
                chain.append(name)
        self.last_chain = ' → '.join(chain)
        if self.overlay:
            self.overlay_event()

    def observe(self, row):
        data = dict(row)
        event = data.pop('event')
        data['trace_seq'] = data.pop('seq')
        data['trace_ms'] = data.pop('ms')
        self.journal.emit(event, **data)
        identifier = row.get('touch_id')
        if event == 'focus' and row['focused']:
            self.performance.response('focus', identifier)
            self.performance.feedback('focus', identifier)
            if identifier is not None:
                self.routes.accept(identifier, row['widget'], definitive=True)
        if event == 'touch_target':
            self.routes.accept(identifier, row['widget'], definitive=True)
            self.performance.response('button_pressed', identifier)
        if event == 'focus' and not row['focused']:
            self.journal.flush_inputs(row['widget'].get('field'), force=True)
        if event == 'motion_begin':
            self.performance.touch_begin(identifier)
            self.routes.begin(identifier)
            self.display_touch_id = str(identifier)
            self.last_touch = [
                row['normalized'][0] * Window.width,
                row['normalized'][1] * Window.height,
            ]
        if event == 'touch_accepted':
            self.routes.accept(identifier, row['widget'])
        if identifier is not None:
            self.refresh_route(identifier)
        if event == 'motion_end':
            Clock.schedule_once(lambda dt, key=identifier: self.finish_route(key), 0)

    @phase('keyboard_probe')
    def native_keyboard_state(self, dt):
        from .keyboard_probe_policy import should_poll

        gesture = self.scroll_observer.metrics.current
        if self.skip_closed_keyboard_poll_on_scroll and not should_poll(
            scrolling=gesture is not None and gesture.get('slop_crossed') is not None,
            focused=any(w.focus for w in self.app.inputs.values()),
            last_state=self.native_state,
        ):
            self.keyboard_probe_skips += 1
            return
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
            text=(self.last_consumer or 'Touch-Diagnose aktiv')
            + '\n'
            + self.last_chain,
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
        self.frame_profiler.queue_inventory(self.app.root_box, self.app.vm.step + 1)
        self.scroll_observer.attach(scroll, 'step' + str(self.app.vm.step + 1))

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
            'scroll_summary': self.scroll_observer.summary(),
            'viewport_native_read_counters': {
                key: getattr(self.app.keyboard_viewport, key, None)
                for key in [
                    'native_reads',
                    'native_reads_while_touch',
                    'deferred_native_reads',
                ]
            },
            'keyboard_diagnostic_poll': {
                'skipped_closed_during_scroll': self.keyboard_probe_skips,
                'policy_enabled': self.skip_closed_keyboard_poll_on_scroll,
            },
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
        popup = ModalView(
            size_hint=(0.95, 0.88),
            auto_dismiss=False,
            background='',
            background_color=rgba('surface'),
        )
        layout = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(8))
        layout.add_widget(self.app.label(title))
        buttons = {}
        for label, action in actions:

            def selected(action=action):
                popup.dismiss(animation=False)
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
        popup.open(animation=False)
        self.trace.attach_tree(popup)
        return popup

    def menu(self):
        self.journal.emit('debug_menu_open')
        actions = [
            (
                'Bericht: Vollständig'
                if self.full_report
                else 'Bericht: Kurzbericht (Standard)',
                self.choose_report_mode,
            ),
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
        if self.app.load_mode.available:
            actions.append(('Belastungstest (nur Test-Build)', self.load_menu))
        actions.append(('Schließen', lambda: None))
        self.popup('Debug – nur auf diesem Gerät', actions)

    def load_menu(self):
        if not self.app.load_mode.available:
            return
        self.popup(
            'Nur Testdaten – keine Inventarfunktion',
            [
                (
                    'Zusatzfelder aus'
                    if self.app.load_mode.enabled
                    else 'Zusatzfelder an',
                    lambda: self.app.set_load_mode(not self.app.load_mode.enabled),
                ),
                ('300 Ark-Zeilen', lambda: self.app.open_load_list('arks')),
                ('100 Teile-Zeilen', lambda: self.app.open_load_list('inventory')),
                ('Schließen', lambda: None),
            ],
        )

    def choose_report_mode(self):
        def choose(full):
            self.full_report = full
            self.journal.emit('report_mode', full=full)
            self.menu()

        self.popup(
            'Berichtsart',
            [
                ('Kurzbericht (Standard)', lambda: choose(False)),
                ('Vollständig', lambda: choose(True)),
                ('Abbrechen', self.menu),
            ],
        )

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

    def export(self, mode):
        if self.export_future is not None and not self.export_future.done():
            self.popup('Bericht wird erstellt …', [('Schließen', lambda: None)])
            return
        token = self.performance.start('export', mode=mode)
        self.journal.emit('report_export_requested', mode=mode, full=self.full_report)
        device, state, full = self.device(), self.state(), self.full_report
        share_context = (
            android_share_context()
            if platform == 'android' and mode == 'share'
            else None
        )

        def work():
            import threading

            self.journal.emit('export_worker', thread=threading.current_thread().name)
            report = self.journal.report(device, state, full=full)
            filename = self.journal.filename()
            if mode == 'clipboard':
                return report, filename, 'In Zwischenablage kopiert.'
            if platform == 'android':
                destination = (
                    android_download(report, filename)
                    if mode == 'downloads'
                    else android_share(report, filename, context=share_context)
                )
            else:
                destination = desktop_report(report, filename)
            return None, filename, destination

        self.export_future = self.export_pool.submit(work)

        def complete(future):
            completed_at = self.performance.clock()

            def finish(dt):
                if self.stopped:
                    return
                try:
                    report, filename, destination = future.result()
                    if mode == 'clipboard':
                        Clipboard.copy(report)
                    self.journal.emit(
                        'report_export_complete', mode=mode, filename=filename
                    )
                    self.performance.finish(token, completed_at=completed_at)
                    if platform != 'android' or mode != 'share':
                        self.popup(destination, [('Schließen', lambda: None)])
                except Exception as error:
                    self.performance.finish(
                        token, failed=True, completed_at=completed_at
                    )
                    self.journal.exception(error, caught=True)
                    self.popup(
                        'Fehler protokolliert – bitte Zwischenablage oder Teilen versuchen.',
                        [('Zurück', self.menu)],
                    )

            Clock.schedule_once(finish, 0)

        self.export_future.add_done_callback(complete)

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
        self.stopped = True
        self.export_pool.shutdown(wait=True, cancel_futures=True)
        self.scroll_observer.stop()
        self.frame_profiler.stop()
        self.touch_intent.stop()
        Window.unbind(on_flip=self.performance.frame)
        self.journal.flush_inputs(force=True)
        self.journal.emit('app_stop')
        self.journal.close()
        ExceptionManager.remove_handler(self.exception_handler)
