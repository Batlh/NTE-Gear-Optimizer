"""CI emulator: actual adb taps/swipes plus read-only Kivy observations."""

import json
import os
from pathlib import Path
from android_ime_state import read_ime_state, current_editor_input_type
import subprocess
import time
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from nte_gear_optimizer_app.probe_protocol import decode_probe

assert os.environ.get('GITHUB_ACTIONS') == 'true'
out = Path('build/emulator_touch')
out.mkdir(parents=True, exist_ok=True)


def adb(*args):
    return subprocess.check_output(
        ['adb', *args], text=True, encoding='utf-8', errors='replace'
    )


def app_logs(tail=None):
    process = subprocess.run(
        ['adb', 'shell', 'pidof', 'io.github.batlh.nte_gear_optimizer'],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
    )
    pids = process.stdout.strip().split()
    assert process.returncode == 0 and len(pids) == 1 and pids[0].isdigit(), (
        'App process not running or ambiguous'
    )
    args = ['logcat', '-d', '--pid=' + pids[0]]
    if tail is not None:
        args += ['-t', str(tail)]
    return adb(*args)


def state():
    return decode_probe(app_logs(3000))


def fresh():
    time.sleep(1.2)
    return state()


def point(rect, s):
    x, y, w, h = rect
    # Android content origin is below the status bar; Kivy y runs upwards.
    return int(s['frame'][0] + x + w / 2), int(
        s['frame'][1] + s['window'][1] - y - h / 2
    )


def tap(rect, s):
    x, y = point(rect, s)
    adb('shell', 'input', 'tap', str(x), str(y))


def swipe(rect, s, reverse=False):
    # Software-rendered CI can coalesce a 280 ms gesture into one sample.
    # Use an actual one-second adb gesture so down/move/up reach SDL frames.
    x, y, w, h = rect
    cx = int(s['frame'][0] + x + w / 2)
    top = int(s['frame'][1] + s['window'][1] - (y + h))
    start, end = (0.25, 0.80) if reverse else (0.80, 0.25)
    adb(
        'shell',
        'input',
        'swipe',
        str(cx),
        str(top + h * start),
        str(cx),
        str(top + h * end),
        '1000',
    )


def screenshot(name):
    data = subprocess.check_output(['adb', 'exec-out', 'screencap', '-p'])
    (out / (name + '.png')).write_bytes(data)


def visible(rect, viewport):
    if rect is None:
        return False
    x, y, w, h = rect
    vx, vy, vw, vh = viewport
    return x >= vx - 2 and x + w <= vx + vw + 2 and y >= vy - 2 and y + h <= vy + vh + 2


def open_list(label):
    s = state()
    previous = None
    stable = 0
    for _ in range(24):
        r = s['selectors'][label]['rect']
        viewport = s['page_scroll']
        if visible(r, viewport):
            if (
                previous is not None
                and max(abs(a - b) for a, b in zip(r, previous)) < 1
            ):
                stable += 1
            else:
                stable = 0
            previous = r
            if stable >= 2:
                tap(r, s)
                break
        else:
            stable = 0
            previous = None
            swipe(viewport, s, reverse=r[1] + r[3] > viewport[1] + viewport[3])
        s = fresh()
    else:
        raise AssertionError('Selector not reachable: ' + label)
    s = fresh()
    assert s.get('modal', {}).get('title') == label, (label, s)
    x, y, w, h = s['modal']['bounds']
    assert (
        x >= 0
        and y >= 0
        and x + w <= s['window'][0] + 1
        and y + h <= s['window'][1] + 1
    )
    return s


def nudge_option(position, viewport, s):
    # A full-page corrective swipe overshot the last row repeatedly in the
    # captured ZERO failure. Correct only the measured clipped edge, using
    # a genuine gesture larger than ScrollView's recognition threshold.
    x, y, w, h = viewport
    lower_gap = max(0, y - position[1])
    upper_gap = max(0, position[1] + position[3] - (y + h))
    threshold = s['modal']['scroll_distance']
    distance = min(
        h * 0.35, max(2 * threshold + 8, lower_gap + upper_gap + threshold + 8)
    )
    cx, cy = point(viewport, s)
    direction = 1 if lower_gap > 0 else -1
    adb(
        'shell',
        'input',
        'swipe',
        str(cx),
        str(round(cy + direction * distance / 2)),
        str(cx),
        str(round(cy - direction * distance / 2)),
        '600',
    )
    edge_corrections.append(
        {
            'row': position,
            'viewport': viewport,
            'lower_gap': lower_gap,
            'upper_gap': upper_gap,
            'distance': distance,
            'actual_adb_gesture': True,
        }
    )


def settled_option(expected):
    # Overscroll rebounds after adb swipe. Tap coordinates must refer to the
    # settled geometry, not an earlier snapshot taken during that rebound.
    previous = None
    stable = 0
    for _ in range(20):
        s = fresh()
        modal = s.get('modal')
        assert modal, 'Selection closed before tapping the requested option'
        row = next(r for r in modal['rows'] if r['id'] == expected)
        position = row['rect']
        if position is None:
            previous, stable = None, 0
            swipe(modal['scroll'], s)
            continue
        if (
            previous is not None
            and max(abs(a - b) for a, b in zip(position, previous)) < 1
        ):
            stable += 1
        else:
            stable = 0
        previous = position
        if stable >= 2 and not modal['touch_active']:
            if visible(position, modal['scroll']):
                return s, row
            # Rebound can settle a few pixels before the edge. A real user
            # can swipe again; do that rather than tapping a clipped option.
            nudge_option(position, modal['scroll'], s)
            stable = 0
            previous = None
    raise AssertionError('Option geometry did not settle: ' + str(expected))


def choose(label, identifier=None, last=False):
    s = open_list(label)
    expected = s['modal']['rows'][-1]['id'] if last else identifier
    before = s['modal']['scroll_y']
    for _ in range(25):
        row = next(r for r in s['modal']['rows'] if r['id'] == expected)
        if visible(row['rect'], s['modal']['scroll']):
            break
        swipe(s['modal']['scroll'], s)
        s = fresh()
    else:
        raise AssertionError('Last option unreachable: ' + label)
    if last:
        # A real swipe even for short lists; no option may escape the viewport.
        swipe(s['modal']['scroll'], s)
        s = fresh()
        row = next(r for r in s['modal']['rows'] if r['id'] == expected)
    s, row = settled_option(expected)
    if last:
        screenshot('selection_' + str(len(evidence)))
        # Screenshot transport itself takes time; acquire settled coordinates
        # again before the actual tap. Never retry a wrong selection as PASS.
        s, row = settled_option(expected)
    assert visible(row['rect'], s['modal']['scroll'])
    scrolled = s['modal']['scroll_y']
    tap(row['rect'], s)
    s = fresh()
    assert 'modal' not in s
    assert s['selectors'][label]['selected'] == expected, (label, expected, s)
    if last:
        evidence.append(
            {
                'list': label,
                'last_id': expected,
                'selected': True,
                'bounded': True,
                'scroll_before': before,
                'scroll_after': scrolled,
            }
        )
    return s


evidence = []
edge_corrections = []
try:
    probe_path = Path('build/a3_probe_apk.json')
    probe = (
        json.loads(probe_path.read_text(encoding='utf-8'))
        if probe_path.exists()
        else None
    )
    apk = Path(probe['apk']) if probe else next(Path('emulator_apk').rglob('*.apk'))
    import zipfile, tarfile, io, hashlib

    with zipfile.ZipFile(apk) as archive:
        with tarfile.open(
            fileobj=io.BytesIO(archive.read('assets/private.tar')), mode='r:*'
        ) as package:
            metadata = json.load(package.extractfile('BUILD_METADATA.json'))
    assert metadata['commit'] == os.environ.get(
        'NTE_EXPECTED_APP_COMMIT',
        probe['metadata']['commit'] if probe else os.environ['GITHUB_SHA'],
    )
    assert metadata['emulator_test_only'] is True
    for relative, digest in metadata['files'].items():
        if relative.startswith(('nte_gear_optimizer/', 'nte_gear_optimizer_app/')):
            assert (
                hashlib.sha256((Path('src') / relative).read_bytes()).hexdigest()
                == digest
            ), relative
    adb('install', '-r', str(apk))
    installed_imes = adb('shell', 'ime', 'list', '-s').splitlines()
    latin_imes = [name.strip() for name in installed_imes if 'latin' in name.lower()]
    assert latin_imes, 'No installed Latin soft keyboard in emulator image'
    default_ime = adb(
        'shell', 'settings', 'get', 'secure', 'default_input_method'
    ).strip()
    keyboard = default_ime if default_ime in latin_imes else latin_imes[0]
    (out / 'keyboard_setup.json').write_text(
        json.dumps({'installed': installed_imes, 'selected': keyboard}, indent=2),
        encoding='utf-8',
        newline='\n',
    )
    adb('shell', 'ime', 'enable', keyboard)
    adb('shell', 'ime', 'set', keyboard)
    adb('shell', 'settings', 'put', 'secure', 'show_ime_with_hard_keyboard', '1')
    adb('logcat', '-c')
    adb(
        'shell',
        'am',
        'start',
        '-n',
        'io.github.batlh.nte_gear_optimizer/org.kivy.android.PythonActivity',
        '--ez',
        'nte_ci_test',
        'true',
    )
    for _ in range(30):
        time.sleep(1)
        try:
            s = state()
            break
        except AssertionError:
            pass
    else:
        raise AssertionError('App failed to start')
    choose('Charakter', last=True)
    choose('Ark', last=True)
    choose('Profil', last=True)
    choose('Leistungszweig', last=True)
    choose('Leistungstyp', last=True)
    choose('Leistungstyp', 'DAMAGE')
    choose('Skalierung', last=True)
    choose('Skalierung', 'ANG')
    choose('Krit möglich?', last=True)
    choose('Bruch relevant?', last=True)
    choose('Zyklusreaktion', last=True)
    assert len(evidence) == 9
    # Cancel must preserve selection.
    s = open_list('Charakter')
    old = s['character_id']
    tap(s['modal']['cancel'], s)
    s = fresh()
    assert s['character_id'] == old
    # Integer-only level: reach through real page gestures, not UI mutation.
    for _ in range(24):
        field = s['inputs']['level:ArkLevel']
        if visible(field['rect'], s['page_scroll']):
            break
        swipe(s['page_scroll'], s, reverse=field['rect'][1] > s['page_scroll'][1])
        s = fresh()
    else:
        raise AssertionError('Ark level field unreachable')
    tap(field['rect'], s)
    time.sleep(2)
    level_dump = adb('shell', 'dumpsys', 'input_method')
    (out / 'ime_integer.txt').write_text(level_dump, encoding='utf-8', newline='\n')
    assert current_editor_input_type(level_dump) == 2
    screenshot('integer_keyboard')
    adb('shell', 'input', 'text', '80')
    adb('shell', 'input', 'keyevent', '66')
    s = fresh()
    assert s['inputs']['level:ArkLevel']['text'] == '80'
    tap(s['next'], s)
    s = fresh()
    assert s['step'] == 1
    field = s['inputs']['current:ScaleDirect']
    tap(field['rect'], s)
    time.sleep(2)
    dump = adb('shell', 'dumpsys', 'input_method')
    (out / 'ime_open.txt').write_text(dump, encoding='utf-8', newline='\n')
    open_ime_state = read_ime_state(dump)
    assert open_ime_state['shown'] is True, 'IME closed after short tap'
    assert current_editor_input_type(dump) == 0x3002, (
        'Decimal/signed flags missing from actual editor'
    )
    adb('shell', 'input', 'text', '2560')
    s = fresh()
    field = s['inputs']['current:ScaleDirect']
    assert field['text'] == '2560' and field['focus'], field
    screenshot('keyboard_open')
    # The visible app comma button must work on keyboards without a comma key.
    tap(s['decimal_buttons']['current:ScaleDirect'], s)
    adb('shell', 'input', 'text', '5')
    s = fresh()
    decimal_field = s['inputs']['current:ScaleDirect']
    assert decimal_field['text'] == '2560,5' and decimal_field['focus']
    assert read_ime_state(adb('shell', 'dumpsys', 'input_method'))['shown']
    screenshot('decimal_comma_button')
    for _ in range(len(decimal_field['text'])):
        adb('shell', 'input', 'keyevent', '67')
    adb('shell', 'input', 'text', '2.560')
    s = fresh()
    ambiguous = s['inputs']['current:ScaleDirect']
    assert ambiguous['text'] == '2.560' and 'Tausenderpunkt' in ambiguous['hint'], (
        ambiguous
    )
    screenshot('thousands_point_hint')
    # Assignment step 6 requires the real screenshot as visibility evidence.
    # Android native surface panning is not represented by Kivy widget/matrix
    # coordinates here. Do not manufacture a visual PASS from those coordinates.
    # Builder must inspect this exact hashed screenshot before accepting H01.
    keyboard_render_evidence = {
        'field_logical_rect': field['rect'],
        'frame': s['frame'],
        'render_origin': s['render_origin'],
        'automatic_coordinate_check': 'UNVERIFIED_NOT_SCREEN_COORDINATES',
        'required_visual_check': 'PENDING_BUILDER_SCREENSHOT_REVIEW',
    }
    adb('shell', 'input', 'keyevent', '66')
    s = fresh()
    assert not s['inputs']['current:ScaleDirect']['focus']
    closed_dump = adb('shell', 'dumpsys', 'input_method')
    (out / 'ime_closed.txt').write_text(closed_dump, encoding='utf-8', newline='\n')
    closed_ime_state = read_ime_state(closed_dump)
    assert closed_ime_state['shown'] is False, 'IME still shown after Done'
    old = s['scroll_y']
    swipe(s['page_scroll'], s)
    s = fresh()
    assert abs(s['scroll_y'] - old) > 0.001, 'Page swipe did not scroll'
    devices = sorted({event['device'] for event in s.get('motions', [])})
    assert 'sdl' in devices and 'mouse' not in devices, (
        'Duplicate Android mouse provider still active',
        devices,
    )
    report = {
        'status': 'AUTOMATED_PASS_VISUAL_REVIEW_PENDING',
        'android_input_devices': devices,
        'app_source_commit': metadata['commit'],
        'test_driver_commit': os.environ['GITHUB_SHA'],
        'selectors': evidence,
        'cancel_preserved': True,
        'short_tap_ime_open_after_2_seconds': True,
        'entered_text': '2560',
        'numeric_keyboard': {
            'actual_decimal_flags': 0x3002,
            'actual_level_flags': 2,
            'comma_button_text': '2560,5',
            'ambiguous_input_text': '2.560',
            'ambiguous_input_hint': ambiguous['hint'],
        },
        'focused_field_visible': None,
        'done_defocuses': True,
        'done_closes_ime': True,
        'ime_state': {'open': open_ime_state, 'after_done': closed_ime_state},
        'keyboard_render_evidence': keyboard_render_evidence,
        'emulator_keyboard': keyboard,
        'page_swipe_scrolls': True,
        'samsung_keyboard': 'UNVERIFIED: emulator keyboard differs from Samsung',
    }
    (out / 'core_touch_result.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
        newline='\n',
    )
    # Check the ancillary launcher image AFTER the actual core touch tests.
    # Reload its first-boot icon database; never change application state to
    # manufacture an icon or bypass the real package manager.
    adb('shell', 'am', 'force-stop', 'com.google.android.apps.nexuslauncher')
    adb('shell', 'input', 'keyevent', '3')
    time.sleep(3)
    adb('shell', 'input', 'swipe', '540', '1700', '540', '400', '400')
    for _ in range(8):
        time.sleep(2)
        adb('shell', 'uiautomator', 'dump', '/sdcard/nte_launcher.xml')
        launcher = adb('shell', 'cat', '/sdcard/nte_launcher.xml')
        if 'NTE Gear' in launcher:
            break
        adb('shell', 'input', 'swipe', '540', '1500', '540', '600', '350')
    (out / 'launcher.xml').write_text(launcher, encoding='utf-8', newline='\n')
    screenshot('launcher_app_icon')
    assert 'NTE Gear' in launcher, 'Installed app icon not found after launcher reload'
    report['launcher_icon'] = True
    (out / 'result.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
        newline='\n',
    )
finally:
    (out / 'edge_corrections.json').write_text(
        json.dumps(edge_corrections, indent=2), encoding='utf-8', newline='\n'
    )
    if 'probe' in globals() and probe:
        (out / 'native_source_binding.json').write_text(
            json.dumps(probe, indent=2), encoding='utf-8', newline='\n'
        )
    (out / 'logcat.txt').write_text(adb('logcat', '-d'), encoding='utf-8', newline='\n')
    screenshot('last_state')
    try:
        (out / 'last_state.json').write_text(
            json.dumps(state(), indent=2), encoding='utf-8', newline='\n'
        )
    except AssertionError:
        pass
