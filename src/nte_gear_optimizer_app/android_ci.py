"""Read-only UI observations, enabled ONLY in the emulator-only CI APK.

The delivered arm64 APK has emulator_test_only=false and never enables this.
No user-file persistence, export or runtime network access is introduced.
"""

import json
import base64
import zlib
from pathlib import Path


def install_probe(app):
    metadata = json.loads(Path('BUILD_METADATA.json').read_text(encoding='utf-8'))
    if not metadata.get('emulator_test_only'):
        return
    from jnius import autoclass

    activity = autoclass('org.kivy.android.PythonActivity').mActivity
    if not activity.getIntent().getBooleanExtra('nte_ci_test', False):
        return
    from kivy.clock import Clock
    from kivy.core.window import Window

    def rect(widget):
        x, y = widget.to_window(*widget.pos)
        return [
            round(x, 2),
            round(y, 2),
            round(widget.width, 2),
            round(widget.height, 2),
        ]

    def snapshot(dt):
        frame = autoclass('android.graphics.Rect')()
        activity.getWindow().getDecorView().getWindowVisibleDisplayFrame(frame)
        state = {
            'window': list(Window.size),
            'frame': [frame.left, frame.top, frame.right, frame.bottom],
            'step': app.vm.step,
            'scroll_y': app.scroll.scroll_y,
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
        if app.active_selector:
            title, popup, scroll, cancel = app.active_selector
            state['modal'] = {
                'title': title,
                'bounds': rect(popup),
                'scroll': rect(scroll),
                'scroll_y': scroll.scroll_y,
                'cancel': rect(cancel),
                'rows': [
                    {'id': value, 'name': name, 'rect': rect(w)}
                    for value, name, w in app.selector_rows
                ],
            }
        print(
            'NTE_CI_STATE='
            + base64.b64encode(
                zlib.compress(json.dumps(state, ensure_ascii=True).encode('utf-8'))
            ).decode('ascii'),
            flush=True,
        )

    Clock.schedule_interval(snapshot, 0.4)
