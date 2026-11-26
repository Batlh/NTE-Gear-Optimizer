"""CI emulator: actual adb taps/swipes plus read-only Kivy observations."""

import json
import base64
import zlib
import os
from pathlib import Path
import re
import subprocess
import time

assert os.environ.get('GITHUB_ACTIONS') == 'true'
out = Path('build/emulator_touch')
out.mkdir(parents=True, exist_ok=True)


def adb(*args):
    return subprocess.check_output(
        ['adb', *args], text=True, encoding='utf-8', errors='replace'
    )


def state():
    lines = adb('logcat', '-d', '-t', '3000').splitlines()
    for line in reversed(lines):
        if 'NTE_CI_STATE=' in line:
            return json.loads(
                zlib.decompress(base64.b64decode(line.split('NTE_CI_STATE=', 1)[1]))
            )
    raise AssertionError('No emulator-only UI observation received')


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
        if (
            previous is not None
            and max(abs(a - b) for a, b in zip(position, previous)) < 1
        ):
            stable += 1
        else:
            stable = 0
        previous = position
        if stable >= 2 and not modal['touch_active']:
            assert visible(position, modal['scroll']), (
                expected,
                position,
                modal['scroll'],
            )
            return s, row
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
        assert visible(row['rect'], s['modal']['scroll'])
    s, row = settled_option(expected)
    if last:
        screenshot('selection_' + str(len(evidence)))
        # Screenshot transport itself takes time; acquire settled coordinates
        # again before the actual tap. Never retry a wrong selection as PASS.
        s, row = settled_option(expected)
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
try:
    apk = next(Path('emulator_apk/bin').glob('*.apk'))
    import zipfile, tarfile, io, hashlib

    with zipfile.ZipFile(apk) as archive:
        with tarfile.open(
            fileobj=io.BytesIO(archive.read('assets/private.tar')), mode='r:*'
        ) as package:
            metadata = json.load(package.extractfile('BUILD_METADATA.json'))
    assert metadata['commit'] == os.environ.get(
        'NTE_EXPECTED_APP_COMMIT', os.environ['GITHUB_SHA']
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
    tap(s['next'], s)
    s = fresh()
    assert s['step'] == 1
    field = s['inputs']['current:ScaleDirect']
    tap(field['rect'], s)
    time.sleep(2)
    dump = adb('shell', 'dumpsys', 'input_method')
    (out / 'ime_open.txt').write_text(dump, encoding='utf-8', newline='\n')
    assert re.search(r'(mInputShown|isInputViewShown|mIsInputViewShown)=true', dump), (
        'IME closed after short tap'
    )
    adb('shell', 'input', 'text', '2560')
    s = fresh()
    field = s['inputs']['current:ScaleDirect']
    assert field['text'] == '2560' and field['focus'], field
    screenshot('keyboard_open')
    # Visible display frame bottom is the top of IME while it is shown.
    fx, fy = point(field['rect'], s)
    assert s['frame'][1] <= fy < s['frame'][3], ('Focused field covered by IME', s)
    adb('shell', 'input', 'keyevent', '66')
    s = fresh()
    assert not s['inputs']['current:ScaleDirect']['focus']
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
        'status': 'PASS',
        'android_input_devices': devices,
        'app_source_commit': metadata['commit'],
        'test_driver_commit': os.environ['GITHUB_SHA'],
        'selectors': evidence,
        'cancel_preserved': True,
        'short_tap_ime_open_after_2_seconds': True,
        'entered_text': '2560',
        'focused_field_visible': True,
        'done_defocuses': True,
        'page_swipe_scrolls': True,
        'samsung_keyboard': 'UNVERIFIED: emulator uses AOSP keyboard',
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
    (out / 'logcat.txt').write_text(adb('logcat', '-d'), encoding='utf-8', newline='\n')
    screenshot('last_state')
    try:
        (out / 'last_state.json').write_text(
            json.dumps(state(), indent=2), encoding='utf-8', newline='\n'
        )
    except AssertionError:
        pass
