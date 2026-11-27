"""Short actual-UI Android export diagnosis; never inject application state."""

import json
import time
import traceback

import a3_android_common as ui


def action(label):
    s = ui.fresh()
    ui.tap(s['debug']['buttons'][label], s)
    time.sleep(1)


result = {'status': 'PENDING'}
try:
    probe = json.loads(ui.Path('build/a3_probe_apk.json').read_text(encoding='utf-8'))
    ui.adb('install', '-r', probe['apk'])
    ui.adb('logcat', '-c')
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
        '--ez',
        'nte_a3_test_exception',
        'true',
    )
    for _ in range(40):
        time.sleep(1)
        try:
            s = ui.state()
            break
        except AssertionError:
            pass
    else:
        raise AssertionError('No UI observations')
    ui.tap(s['debug_button'], s)
    action('Debug-Bericht exportieren')
    ui.record('export_only_privacy')
    action('Fortfahren')
    time.sleep(2)
    (ui.out / 'share_chooser.png').write_bytes(
        ui.subprocess.check_output(['adb', 'exec-out', 'screencap', '-p'])
    )
    activity = ui.adb('shell', 'dumpsys', 'activity', 'activities')
    assert 'ChooserActivity' in activity, (
        'Share chooser did not open; inspect private_debug for actual cause'
    )
    ui.adb('shell', 'input', 'keyevent', '4')
    s = ui.fresh()
    ui.tap(s['debug_button'], s)
    action('In Downloads speichern')
    action('Fortfahren')
    ui.record('export_only_downloads')
    names = ui.adb('shell', 'ls', '/sdcard/Download').splitlines()
    name = max(
        n.strip()
        for n in names
        if n.startswith('NTE_Debugbericht_') and n.endswith('.txt')
    )
    data = ui.subprocess.check_output(
        ['adb', 'exec-out', 'cat', '/sdcard/Download/' + name]
    )
    payload = json.loads(data.decode('utf-8').split('--- NTE_DEBUG_JSON ---')[1])
    assert payload['format'] == 'NTE_DEBUG_V1'
    assert any(
        e['event'] == 'performance' and e['operation'] == 'export'
        for e in payload['events']
    )
    (ui.out / ('Downloads_' + name)).write_bytes(data)
    result = {
        'status': 'PASS',
        'share_chooser': True,
        'downloads_json_roundtrip': True,
        'completed_share_export_timing': True,
        'apk_commit': probe['metadata']['commit'],
    }
except Exception:
    result = {'status': 'FAIL', 'stacktrace': traceback.format_exc()}
finally:
    ui.collect_private_debug()
    (ui.out / 'result.json').write_text(
        json.dumps(result, indent=2), encoding='utf-8', newline='\n'
    )
    (ui.out / 'logcat.txt').write_text(
        ui.adb('logcat', '-d'), encoding='utf-8', newline='\n'
    )
assert result['status'] == 'PASS', result
