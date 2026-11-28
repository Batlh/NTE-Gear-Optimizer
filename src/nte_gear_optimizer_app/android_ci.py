"""Read-only UI observations, enabled ONLY in the emulator-only CI APK.

The delivered arm64 APK has emulator_test_only=false and never enables this.
The CI-only performance command toggles diagnostic logging, never model/focus/input
values. No user-file persistence or runtime network access is introduced.
"""

import json
from .probe_protocol import encode_probe
from pathlib import Path


def install_probe(app):
    metadata = json.loads(Path('BUILD_METADATA.json').read_text(encoding='utf-8'))
    if not metadata.get('emulator_test_only'):
        return
    from jnius import autoclass, cast

    activity = autoclass('org.kivy.android.PythonActivity').mActivity
    if not activity.getIntent().getBooleanExtra('nte_ci_test', False):
        return
    from kivy.clock import Clock
    from kivy.core.window import Window
    from collections import deque

    # This command is unavailable in the delivered ARM64 package. Both the
    # emulator-only build flag and the explicit test launch above are required.
    perf_state = {'logging': True, 'boundaries': [], 'flip_count': 0}

    def flip_count(*args):
        perf_state['flip_count'] += 1

    Window.bind(on_flip=flip_count)

    def performance_intent(intent):
        if intent.hasExtra('nte_ci_keyboard_scroll_skip'):
            skip = bool(intent.getBooleanExtra('nte_ci_keyboard_scroll_skip', True))
            Clock.schedule_once(
                lambda dt: setattr(
                    app.debug, 'skip_closed_keyboard_poll_on_scroll', skip
                ),
                0,
            )
        if intent.hasExtra('nte_ci_frame_profiling'):
            enabled_profile = bool(
                intent.getBooleanExtra('nte_ci_frame_profiling', True)
            )
            Clock.schedule_once(
                lambda dt: setattr(
                    app.debug.frame_profiler, 'enabled', enabled_profile
                ),
                0,
            )
        if not intent.hasExtra('nte_ci_perf_logging'):
            return
        enabled = bool(intent.getBooleanExtra('nte_ci_perf_logging', True))

        def change(dt):
            journal = app.debug.journal
            before = journal.seq
            journal.enabled = enabled
            perf_state['logging'] = enabled
            perf_state['boundaries'].append({'enabled': enabled, 'seq': before})

        Clock.schedule_once(change, 0)

    from android import activity as android_activity

    android_activity.bind(on_new_intent=performance_intent)
    a3 = activity.getIntent().getBooleanExtra('nte_a3_cause', False)
    trace = None
    if a3:
        from .diagnostic_trace import InputTrace

        trace = InputTrace(
            app,
            lambda row: print(
                'NTE_A3_EVENT=' + json.dumps(row, ensure_ascii=True), flush=True
            ),
        )
        if activity.getIntent().getBooleanExtra('nte_a3_test_exception', False):
            app.debug.test_exception()
        trace.attach_window(Window)
        trace.attach_tree(app.root_box)
        original_render = app.render

        def traced_render(*args, **kwargs):
            original_render(*args, **kwargs)
            trace.attach_tree(app.root_box)

        app.render = traced_render

    def native_surface():
        # Actual Android screen coordinates; never infer native IME panning
        # from the Kivy matrix or the window's visible-frame top.
        java_class = autoclass('java.lang.Class')
        surface_type = java_class.forName('android.view.SurfaceView')
        group_type = java_class.forName('android.view.ViewGroup')

        def find(view):
            if surface_type.isInstance(view):
                return view
            if group_type.isInstance(view):
                group = cast('android.view.ViewGroup', view)
                for i in range(group.getChildCount()):
                    found = find(group.getChildAt(i))
                    if found is not None:
                        return found
            return None

        surface = find(activity.getWindow().getDecorView())
        if surface is None:
            return {'error': 'SurfaceView not found'}
        location = [0, 0]
        surface.getLocationOnScreen(location)
        return {
            'screen_rect': [*location, surface.getWidth(), surface.getHeight()],
            'class': str(surface.getClass().getName()),
        }

    motions = deque(maxlen=16)

    def observe_motion(window, kind, touch):
        motions.append(
            {
                'event': kind,
                'sx': getattr(touch, 'sx', None),
                'sy': getattr(touch, 'sy', None),
                'x': getattr(touch, 'x', None),
                'y': getattr(touch, 'y', None),
                'device': str(getattr(touch, 'device', '')),
            }
        )
        return False

    Window.bind(on_motion=observe_motion)

    def rect(widget):
        x, y = widget.to_window(*widget.pos)
        # below_target pans the render matrix without changing logical widget
        # coordinates. Observe the actual matrix; do not reproduce its formula.
        x, y, _ = Window.render_context['modelview_mat'].transform_point(x, y, 0)
        return [
            round(x, 2),
            round(y, 2),
            round(widget.width, 2),
            round(widget.height, 2),
        ]

    sequence = 0

    def snapshot(dt):
        nonlocal sequence
        sequence += 1
        frame = autoclass('android.graphics.Rect')()
        activity.getWindow().getDecorView().getWindowVisibleDisplayFrame(frame)
        state = {
            'window': list(Window.size),
            'visual_window': {
                'root_opacity': app.root.opacity,
                'clearcolor': list(Window.clearcolor),
                'native_decor_alpha': activity.getWindow().getDecorView().getAlpha(),
                'native_window_alpha': activity.getWindow().getAttributes().alpha,
                'window_children': [
                    {
                        'type': type(w).__name__,
                        'opacity': w.opacity,
                        'is_open': getattr(w, '_is_open', None),
                    }
                    for w in Window.children
                ],
            },
            'render_origin': list(
                Window.render_context['modelview_mat'].transform_point(0, 0, 0)
            ),
            'rotation': Window.rotation,
            'softinput_mode': Window.softinput_mode,
            'motions': list(motions),
            'frame': [frame.left, frame.top, frame.right, frame.bottom],
            'header': {name: rect(w) for name, w in app.header_widgets.items()},
            'step': app.vm.step,
            'scroll_y': app.scroll.scroll_y,
            'page_scroll': rect(app.scroll),
            'character_id': app.vm.character_id,
            'ark_id': app.vm.ark_id,
            'profile_id': app.vm.profile_id,
            'branch_id': app.vm.branch_id,
            'profile': app.vm.profile(),
            'selectors': {
                label: {
                    'rect': rect(w),
                    'choices': app.selector_specs[label][0],
                    'selected': app.selector_specs[label][1],
                }
                for label, w in app.selector_widgets.items()
            },
            'inputs': {
                group + ':' + field: {'rect': rect(w), 'text': w.text, 'focus': w.focus}
                for (group, field), w in app.inputs.items()
            },
            'next': rect(app.next_button),
            'back': rect(app.back_button),
        }
        if a3:
            summary = app.debug.scroll_observer.summary()
            state['performance_probe'] = {
                **perf_state,
                'display': summary['display'],
                'profiling_enabled': app.debug.frame_profiler.enabled,
                'keyboard_probe_skips': app.debug.keyboard_probe_skips,
                'keyboard_scroll_skip': app.debug.skip_closed_keyboard_poll_on_scroll,
                'refresh_reads': summary['refresh_reads'],
                'refresh_reads_during_gesture': summary['refresh_reads_during_gesture'],
                'display_listener_status': summary['display_listener_status'],
                'physics': summary['physics'],
                'gestures': [
                    {
                        **g,
                        'frame_profile': {
                            k: v
                            for k, v in g.get('frame_profile', {}).items()
                            if k != 'rows'
                            or app.debug.scroll_observer.metrics.current is None
                        },
                    }
                    for g in summary['gestures'][-8:]
                ],
                'journal_seq': app.debug.journal.seq,
                'body_padding': list(app.body.padding),
                'page_id': id(app.body),
                'touch_target': app.debug.last_consumer,
                'touch_chain': app.debug.last_chain,
                'touch_slop_policy': app.debug.touch_intent.policy,
                'touch_intents': app.debug.touch_intent.recent,
                'input_ids': {':'.join(k): id(w) for k, w in app.inputs.items()},
                'viewport_measurement': getattr(
                    app.keyboard_viewport, 'last_measurement', None
                )
                if hasattr(app, 'keyboard_viewport')
                else None,
            }
            state['debug_button'] = rect(app.debug_button)
            state['zeros'] = [rect(widget) for widget in app.zero_buttons]
            state['jumps'] = {
                str(step): rect(widget) for step, widget in app.jump_buttons.items()
            }
            state['result'] = app.vm.last_result
            state['input_hints'] = {
                ':'.join(key): widget.text for key, widget in app.input_hints.items()
            }
            if app.active_debug:
                popup, buttons = app.active_debug
                state['debug'] = {
                    'bounds': rect(popup),
                    'buttons': {label: rect(w) for label, w in buttons.items()},
                }
            try:
                state['native_surface'] = native_surface()
                state['input_visibility'] = {
                    group + ':' + field: trace.describe(widget)
                    for (group, field), widget in app.inputs.items()
                }
                frame_values = [frame.left, frame.top, frame.right, frame.bottom]
                if getattr(app, '_a3_last_frame', None) != frame_values:
                    trace.emit(
                        'native_visible_frame',
                        frame=frame_values,
                        surface=state['native_surface'],
                    )
                    app._a3_last_frame = frame_values
            except Exception as error:
                state['native_surface'] = {'error': type(error).__name__}

        if app.active_selector:
            title, popup, scroll, cancel = app.active_selector
            state['modal'] = {
                'title': title,
                'bounds': rect(popup),
                'scroll': rect(scroll),
                'scroll_y': scroll.scroll_y,
                'scroll_timeout': scroll.scroll_timeout,
                'scroll_distance': scroll.scroll_distance,
                'touch_active': scroll._touch is not None,
                'cancel': rect(cancel),
                'rows': [
                    {'id': value, 'name': name, 'rect': rect(w)}
                    for value, name, w in app.selector_rows
                ],
            }
        for line in encode_probe(state, sequence):
            print(line, flush=True)

    Clock.schedule_interval(snapshot, 0.4)
