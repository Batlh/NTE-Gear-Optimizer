"""CI-only actual input hint and selected-row screenshot after selector regression."""

import json, time
import a3_android_common as ui

ui.adb('shell', 'am', 'force-stop', 'io.github.batlh.nte_gear_optimizer')
ui.adb(
    'shell',
    'am',
    'start',
    '-n',
    'io.github.batlh.nte_gear_optimizer/org.kivy.android.PythonActivity',
    '--ez',
    'nte_ci_test',
    'true',
    '--ez',
    'nte_a3_cause',
    'true',
)
for _ in range(40):
    time.sleep(1)
    try:
        s = ui.state()
        if s['step'] == 0 and 'input_hints' in s:
            break
    except AssertionError, KeyError:
        pass
else:
    raise AssertionError('Fresh visual test session unavailable')
assert s['inputs']['level:ArkLevel']['text'] == ''
s, ime = ui.field('level:ArkLevel', '80.8', 'design_ark_level_hint_without_ark')
assert s['inputs']['level:ArkLevel']['text'] == '80.8'
assert s['input_hints']['level:ArkLevel'] and s['ark_id'] is None
ui.adb('shell', 'input', 'keyevent', '66')
s = ui.fresh()
rect, s = ui.reach(
    lambda s: s['selectors']['Charakter']['rect'], lambda s: s['page_scroll']
)
ui.tap(rect, s)
s, ime = ui.record('design_selector_current')
assert s['modal']['title'] == 'Charakter'
assert any(row['id'] is None for row in s['modal']['rows'])
(ui.out / 'visual_result.json').write_text(
    json.dumps(
        {
            'status': 'PASS',
            'actual_ark_level_input': '80.8',
            'hint_without_ark': True,
            'current_selector': 'Charakter',
            'screenshot_review': 'PENDING_BUILDER',
        },
        indent=2,
    )
    + '\n',
    encoding='utf-8',
    newline='\n',
)
print('Actual input hint and current-selection screenshots captured.')
