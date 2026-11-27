"""Actual Android touches, keyboard transitions, debug sharing and journal."""

import json
import time
import traceback

import a3_android_common as ui


def ime_field(key, value, name):
    before = ui.state()['inputs'][key]['text']
    s, ime = ui.field(key, value, name)
    focused = [key for key, value in s['inputs'].items() if value['focus']]
    assert focused == [key], (key, focused)
    assert s['inputs'][key]['text'] == before + value, (key, before, s['inputs'][key])
    assert ime['shown'] is True, (key, ime)
    return s


def every_part_field(label):
    done = set()
    for _ in range(60):
        s = ui.fresh()
        available = [
            key
            for key in s['inputs']
            if key not in done and s['input_visibility'][key]['tree_visible']
        ]
        if not available:
            return
        key = available[0]
        ime_field(key, str(len(done) + 2), label + '_' + key.replace(':', '_'))
        done.add(key)
    raise AssertionError('Part fields did not stabilise')


def debug_action(label):
    s = ui.fresh()
    tap = s['debug']['buttons'][label]
    ui.tap(tap, s)
    time.sleep(1)


result = {'status': 'PENDING'}
try:
    probe = json.loads(ui.Path('build/a3_probe_apk.json').read_text(encoding='utf-8'))
    ui.adb('install', '-r', probe['apk'])
    imes = ui.adb('shell', 'ime', 'list', '-s').splitlines()
    keyboard = next(i.strip() for i in imes if 'latin' in i.lower())
    ui.adb('shell', 'ime', 'enable', keyboard)
    ui.adb('shell', 'ime', 'set', keyboard)
    ui.adb('shell', 'settings', 'put', 'secure', 'show_ime_with_hard_keyboard', '1')
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
            ui.state()
            break
        except AssertionError:
            pass
    for label, key in [
        ('Leistungstyp', 'DAMAGE'),
        ('Skalierung', 'ANG'),
        ('Krit möglich?', 'TRUE'),
        ('Bruch relevant?', 'FALSE'),
        ('Zyklusreaktion', 'NONE'),
    ]:
        ui.choose(label, key)
    s = ui.fresh()
    ui.tap(s['next'], s)
    s = ui.fresh()
    assert s['step'] == 1
    # Required down/up handoff with the keyboard left open at every tap.
    handoff_events = {}
    for key, value, name in [
        ('current:UniversalPP', '12', 'keyboard_A'),
        ('current:OtherPP', '34', 'keyboard_B_lower'),
        ('current:ElementPP', '56', 'keyboard_C_upper'),
    ]:
        ime_field(key, value, name)
        for line in ui.app_logs(6000).splitlines():
            if 'NTE_A3_EVENT=' in line:
                event = json.loads(line.split('NTE_A3_EVENT=', 1)[1])
                handoff_events[event['seq']] = event
    ordered = [handoff_events[key] for key in sorted(handoff_events)]
    first = next(
        e
        for e in ordered
        if e['event'] == 'focus'
        and e.get('focused')
        and e.get('widget', {}).get('field') == 'current:UniversalPP'
    )
    last = next(
        e
        for e in ordered
        if e['event'] == 'focus'
        and e.get('focused')
        and e.get('widget', {}).get('field') == 'current:ElementPP'
    )
    assert not [
        e
        for e in ordered
        if first['seq'] < e['seq'] <= last['seq']
        and e['event'] in ('request_keyboard_before', 'release_keyboard_before')
    ], ordered
    open_frame = next(
        e
        for e in ordered
        if e['seq'] > first['seq']
        and e['event'] == 'native_visible_frame'
        and e['frame'][3] <= ui.timeline[-1]['state']['frame'][3] + 2
    )
    assert not [
        e
        for e in ordered
        if e['seq'] > open_frame['seq']
        and e['event'] == 'native_visible_frame'
        and e['frame'][3] > open_frame['frame'][3] + 100
    ], ordered
    (ui.out / 'keyboard_handoff_evidence.json').write_text(
        json.dumps(
            {
                'status': 'PASS',
                'no_native_release_request_during_handoff': True,
                'no_ime_hide_frame_during_handoff': True,
                'events': ordered,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
        newline='\n',
    )
    ui.adb('shell', 'input', 'keyevent', '66')
    s = ui.fresh()
    ui.tap(s['next'], s)
    s = ui.fresh()
    assert s['step'] == 2
    every_part_field('ang_all_fields')
    # Same-row handoff and double tap, again without closing IME.
    ime_field('x:UniversalPP', '12', 'pair_left')
    s = ime_field('y:UniversalPP', '34', 'pair_right')
    rect, s = ui.reach(
        lambda s: s['inputs']['y:UniversalPP']['rect'], lambda s: s['page_scroll']
    )
    ui.tap(rect, s)
    time.sleep(0.12)
    ui.tap(rect, ui.state())
    time.sleep(2)
    s, ime = ui.record('same_field_double_tap')
    assert s['inputs']['y:UniversalPP']['focus'] and ime['shown']
    ui.adb('shell', 'input', 'keyevent', '66')
    s = ui.fresh()
    ui.tap(s['back'], s)
    s = ui.fresh()
    ui.tap(s['back'], s)
    s = ui.fresh()
    assert s['step'] == 0
    ui.choose('Skalierung', 'UNBEKANNT')
    s = ui.fresh()
    ui.tap(s['next'], s)
    s = ui.fresh()
    ui.tap(s['next'], s)
    s = ui.fresh()
    every_part_field('no_scale_all_fields')
    ui.adb('shell', 'input', 'keyevent', '66')
    s = ui.fresh()
    assert s['zeros']
    ui.tap(s['zeros'][0], s)
    s = ui.fresh()
    ui.tap(s['next'], s)
    s = ui.fresh()
    assert s['step'] == 3 and s['result'] is not None
    assert '1' in s['jumps'], s['jumps']
    ui.tap(s['jumps']['1'], s)
    s = ui.fresh()
    assert s['step'] == 1
    ui.tap(s['debug_button'], s)
    ui.record('debug_menu')
    debug_action('Touch-Diagnose an')
    # At least one real touch while overlay is enabled.
    ime_field('current:UniversalPP', '7', 'touch_overlay')
    ui.adb('shell', 'input', 'keyevent', '66')
    s = ui.fresh()
    ui.tap(s['debug_button'], s)
    debug_action('Debug-Bericht exportieren')
    ui.record('privacy_notice')
    debug_action('Fortfahren')
    time.sleep(2)
    (ui.out / 'share_chooser.png').write_bytes(
        ui.subprocess.check_output(['adb', 'exec-out', 'screencap', '-p'])
    )
    activity = ui.adb('shell', 'dumpsys', 'activity', 'activities')
    assert 'ChooserActivity' in activity, activity[-5000:]
    files = ui.adb(
        'shell',
        'run-as',
        'io.github.batlh.nte_gear_optimizer',
        'ls',
        'cache/debug_reports',
    ).splitlines()
    filename = max(
        name.strip()
        for name in files
        if name.startswith('NTE_Debugbericht_') and name.endswith('.txt')
    )
    data = ui.subprocess.check_output(
        [
            'adb',
            'exec-out',
            'run-as',
            'io.github.batlh.nte_gear_optimizer',
            'cat',
            'cache/debug_reports/' + filename,
        ]
    )
    (ui.out / filename).write_bytes(data)
    payload = json.loads(data.decode('utf-8').split('\n--- NTE_DEBUG_JSON ---\n')[1])
    events = payload['events']
    for event in [
        'selection',
        'input',
        'focus',
        'touch_accepted',
        'zero_bonus',
        'step',
        'result',
        'native_keyboard_window',
    ]:
        assert any(row['event'] == event for row in events), event
    assert any(
        row['event'] == 'exception' and 'NTE_A3_TEST_EXCEPTION' in row['stacktrace']
        for row in events
    )
    session = payload['events'][-1]['session']
    current = [e['seq'] for e in events if e['session'] == session]
    assert current == sorted(set(current)), current
    assert payload['device']['commit'] == probe['metadata']['commit']
    assert payload['device']['version_code'] > 1002601
    ui.adb('shell', 'input', 'keyevent', '4')
    s = ui.fresh()
    ui.tap(s['debug_button'], s)
    debug_action('In Downloads speichern')
    debug_action('Fortfahren')
    ui.record('downloads_saved')
    names = ui.adb('shell', 'ls', '/sdcard/Download').splitlines()
    download = max(
        name.strip()
        for name in names
        if name.startswith('NTE_Debugbericht_') and name.endswith('.txt')
    )
    downloaded = ui.subprocess.check_output(
        ['adb', 'exec-out', 'cat', '/sdcard/Download/' + download]
    )
    assert (
        json.loads(downloaded.decode('utf-8').split('\n--- NTE_DEBUG_JSON ---\n')[1])[
            'format'
        ]
        == 'NTE_DEBUG_V1'
    )
    (ui.out / ('Downloads_' + download)).write_bytes(downloaded)
    result = {
        'status': 'PASS',
        'apk_commit': probe['metadata']['commit'],
        'share_chooser': True,
        'downloads_without_permission': True,
        'report_file': filename,
        'report_json_roundtrip': True,
    }
except Exception:
    result = {'status': 'FAIL', 'stacktrace': traceback.format_exc()}
finally:
    logs = ui.app_logs()
    (ui.out / 'logcat.txt').write_text(logs, encoding='utf-8', newline='\n')
    events = [
        json.loads(line.split('NTE_A3_EVENT=', 1)[1])
        for line in logs.splitlines()
        if 'NTE_A3_EVENT=' in line
    ]
    for name, value in [
        ('events.json', events),
        ('timeline.json', ui.timeline),
        ('result.json', result),
    ]:
        (ui.out / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2),
            encoding='utf-8',
            newline='\n',
        )
assert result['status'] == 'PASS', result
