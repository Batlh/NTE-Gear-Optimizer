"""Actual Android touches, keyboard transitions, debug sharing and journal."""

import json
import re
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
    from a5_android_touch_cases import run as h01_cases

    h01_cases(ui)
    ui.record('design_step1_selection')
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
    ui.record('design_step2_values')
    # A real swipe starting on an input must neither focus it nor open IME.
    rect, s = ui.reach(
        lambda s: s['inputs']['current:UniversalPP']['rect'], lambda s: s['page_scroll']
    )
    x, y, width, height = ui.screen_rect(rect, s)
    ui.adb(
        'shell',
        'input',
        'swipe',
        str(round(x + width / 2)),
        str(round(y + height / 2)),
        str(round(x + width / 2)),
        str(round(max(s['frame'][1] + 20, y + height / 2 - 120))),
        '350',
    )
    time.sleep(1)
    swiped, swipe_ime = ui.record('swipe_on_input_no_focus')
    assert not any(v['focus'] for v in swiped['inputs'].values())
    assert not swipe_ime['shown']
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
    s = ui.fresh()
    focused = next(v for v in s['inputs'].values() if v['focus'])
    _, bottom, _, height = ui.screen_rect(focused['rect'], s)
    gap = s['frame'][3] - bottom - height
    density_values = re.findall(
        r'(?:Physical|Override) density:\s*(\d+)', ui.adb('shell', 'wm', 'density')
    )
    assert density_values, 'Native display density unavailable'
    native_density = int(density_values[-1]) / 160
    native_per_window_pixel = s['native_surface']['screen_rect'][3] / s['window'][1]
    gap_dp = gap / (native_density * native_per_window_pixel)
    # The implementation uses dp(8); test a small0..24dp native-screen gap,
    # not a density-dependent fixed32physical-pixel limit.
    assert 0 <= gap_dp <= 24, ('Lower field not just above IME', gap_dp, gap, s)
    ui.record('lowest_field_minimal_ime_gap')
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
    rect, s = ui.reach(lambda s: s['zeros'][0], lambda s: s['page_scroll'])
    ui.tap(rect, s)
    s = ui.fresh()
    ui.tap(s['next'], s)
    s = ui.fresh()
    assert s['step'] == 3 and s['result'] is not None
    ui.record('design_step4_indeterminate')
    assert '1' in s['jumps'], s['jumps']
    rect, s = ui.reach(lambda s: s['jumps']['1'], lambda s: s['page_scroll'])
    ui.tap(rect, s)
    s = ui.fresh()
    assert s['step'] == 1
    ui.tap(s['debug_button'], s)
    ui.record('debug_menu')
    debug_action('Touch-Diagnose an')
    # At least one real touch while overlay is enabled.
    overlay = ime_field('current:UniversalPP', '7', 'touch_overlay')
    target = overlay['performance_probe']['touch_target']
    assert 'TextInput current:UniversalPP' in target, target
    assert 'TextInput' in overlay['performance_probe']['touch_chain']
    ui.adb('shell', 'input', 'keyevent', '66')
    s = ui.fresh()
    ui.tap(s['debug_button'], s)
    # Full regression deliberately selects the complete journal. Default short
    # export is verified separately by the export-only native scenario.
    debug_action('Bericht: Kurzbericht (Standard)')
    debug_action('Vollständig')
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
    assert abs(payload['device']['density'] - native_density) < 0.01
    assert payload['device']['version_code'] > 1004001
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
    downloaded_payload = json.loads(
        downloaded.decode('utf-8').split('\n--- NTE_DEBUG_JSON ---\n')[1]
    )
    assert downloaded_payload['format'] == 'NTE_DEBUG_V1'
    timings = [e for e in downloaded_payload['events'] if e['event'] == 'performance']
    for operation in [
        'render',
        'selector_setup',
        'selector_build',
        'selector_open',
        'calculate',
        'export',
        'touch_to_response_frame',
    ]:
        assert any(e['operation'] == operation for e in timings), operation
    assert downloaded_payload['performance_summary']['slowest_10']
    assert len(downloaded_payload['performance_summary']['slowest_10']) <= 10
    assert all(
        isinstance(e['duration_ms'], (int, float))
        and isinstance(e['over_100_ms'], bool)
        for e in timings
    )
    (ui.out / ('Downloads_' + download)).write_bytes(downloaded)
    # Fresh real-input scenario for the delivered design's positive result.
    # No state injection: selecting, typing and zero buttons use adb touches.
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
            fresh_state = ui.state()
            if (
                fresh_state['step'] == 0
                and fresh_state['inputs']['level:ArkLevel']['text'] == ''
            ):
                break
        except AssertionError:
            pass
    else:
        raise AssertionError('Fresh design screenshot session failed to start')
    for label, key in [
        ('Leistungstyp', 'DAMAGE'),
        ('Skalierung', 'ANG'),
        ('Krit möglich?', 'FALSE'),
        ('Bruch relevant?', 'FALSE'),
        ('Zyklusreaktion', 'NONE'),
    ]:
        ui.choose(label, key)
    s = ui.fresh()
    ui.tap(s['next'], s)
    s = ui.fresh()
    ime_field('current:ScaleDirect', '100', 'design_current_100')
    ui.adb('shell', 'input', 'keyevent', '66')
    s = ui.fresh()
    rect, s = ui.reach(lambda s: s['zeros'][0], lambda s: s['page_scroll'])
    ui.tap(rect, s)
    s = ui.fresh()
    ui.tap(s['next'], s)
    s = ui.fresh()
    ui.record('design_step3_parts')
    for key, value in [
        ('x:ScaleDirect', '10'),
        ('y:ScaleDirect', '20'),
        ('x:ScalingPercentPP', '0'),
        ('y:ScalingPercentPP', '0'),
    ]:
        ime_field(key, value, 'design_part_' + key.replace(':', '_'))
    ui.adb('shell', 'input', 'keyevent', '66')
    s = ui.fresh()
    rect, s = ui.reach(lambda s: s['zeros'][1], lambda s: s['page_scroll'])
    ui.tap(rect, s)
    s = ui.fresh()
    ui.tap(s['next'], s)
    s = ui.fresh()
    assert s['result']['engine']['Verdict'] == 'BETTER', s['result']
    assert s['result']['engine']['VerdictRatio'] == '1.100000000'
    ui.record('design_step4_better')
    result = {
        'status': 'PASS',
        'apk_commit': probe['metadata']['commit'],
        'share_chooser': True,
        'downloads_without_permission': True,
        'report_file': filename,
        'report_json_roundtrip': True,
        'lowest_field_ime_gap_px': gap,
        'lowest_field_ime_gap_dp': gap_dp,
        'native_density_matches_app': True,
        'design_positive_result_actual_input': True,
    }
except Exception:
    result = {'status': 'FAIL', 'stacktrace': traceback.format_exc()}
finally:
    ui.collect_private_debug()
    try:
        logs = ui.app_logs()
    except AssertionError as error:
        result['postmortem_log_note'] = str(error)
        logs = ui.adb('logcat', '-d')
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
