"""Real adb input; inspect pre-fix H01 and keyboard focus/IME sequence."""

import base64
import json
import os
from pathlib import Path
import subprocess
import time
import traceback
import zlib

from android_ime_state import read_ime_state

assert os.environ.get('GITHUB_ACTIONS') == 'true'
out = Path('build/a3_android_cause')
out.mkdir(parents=True, exist_ok=False)
timeline = []
started = time.monotonic()


def adb(*args):
    return subprocess.check_output(
        ['adb', *args], text=True, encoding='utf-8', errors='replace'
    )


def state():
    for line in reversed(adb('logcat', '-d', '-t', '6000').splitlines()):
        if 'NTE_CI_STATE=' in line:
            return json.loads(
                zlib.decompress(base64.b64decode(line.split('NTE_CI_STATE=', 1)[1]))
            )
    raise AssertionError('No read-only UI probe')


def fresh():
    time.sleep(1.1)
    return state()


def screen_rect(rect, s):
    left, top, sw, sh = s['native_surface']['screen_rect']
    ww, wh = s['window']
    x, y, w, h = rect
    return [left + x * sw / ww, top + (wh - y - h) * sh / wh, w * sw / ww, h * sh / wh]


def viewport(rect, s):
    x, y, w, h = screen_rect(rect, s)
    left, top, right, bottom = s['frame']
    return [
        max(left, x),
        max(top, y),
        min(right, x + w) - max(left, x),
        min(bottom, y + h) - max(top, y),
    ]


def visible(rect, view, s):
    x, y, w, h = screen_rect(rect, s)
    vx, vy, vw, vh = viewport(view, s)
    return x >= vx - 1 and y >= vy - 1 and x + w <= vx + vw + 1 and y + h <= vy + vh + 1


def tap(rect, s):
    x, y, w, h = screen_rect(rect, s)
    adb('shell', 'input', 'tap', str(round(x + w / 2)), str(round(y + h / 2)))


def swipe(view, s, reverse=False):
    x, y, w, h = viewport(view, s)
    assert h > 80, ('No scrollable native viewport', s)
    a, b = (0.3, 0.75) if reverse else (0.75, 0.3)
    adb(
        'shell',
        'input',
        'swipe',
        str(round(x + w / 2)),
        str(round(y + h * a)),
        str(round(x + w / 2)),
        str(round(y + h * b)),
        '900',
    )


def reach(get_rect, get_view):
    previous = None
    stable = 0
    for _ in range(28):
        s = fresh()
        rect, view = get_rect(s), get_view(s)
        physical = screen_rect(rect, s)
        if visible(rect, view, s):
            stable = (
                stable + 1
                if previous and max(abs(a - b) for a, b in zip(previous, physical)) < 1
                else 0
            )
            previous = physical
            if stable >= 1:
                return rect, s
        else:
            previous, stable = None, 0
            swipe(view, s, reverse=rect[1] + rect[3] > view[1] + view[3])
    raise AssertionError('Could not reach target through native gestures')


def choose(label, key):
    rect, s = reach(lambda s: s['selectors'][label]['rect'], lambda s: s['page_scroll'])
    tap(rect, s)
    s = fresh()
    assert s['modal']['title'] == label
    rect, s = reach(
        lambda s: next(r['rect'] for r in s['modal']['rows'] if r['id'] == key),
        lambda s: s['modal']['scroll'],
    )
    tap(rect, s)
    s = fresh()
    assert s['selectors'][label]['selected'] == key


def record(name):
    s = state()
    manager = adb('shell', 'dumpsys', 'input_method')
    service = adb('shell', 'dumpsys', 'activity', 'service', 'InputMethod')
    (out / (name + '_input_method.txt')).write_text(
        manager, encoding='utf-8', newline='\n'
    )
    (out / (name + '_service.txt')).write_text(service, encoding='utf-8', newline='\n')
    ime = read_ime_state(manager)
    timeline.append(
        {
            'name': name,
            'ms': round(1000 * (time.monotonic() - started)),
            'state': s,
            'ime': ime,
        }
    )
    (out / (name + '.png')).write_bytes(
        subprocess.check_output(['adb', 'exec-out', 'screencap', '-p'])
    )
    return s, ime


def field(key, value, name):
    rect, s = reach(lambda s: s['inputs'][key]['rect'], lambda s: s['page_scroll'])
    tap(rect, s)
    time.sleep(0.3)
    adb('shell', 'input', 'text', value)
    time.sleep(2)
    return record(name)


result = {'status': 'PENDING'}
try:
    probe = json.loads(Path('build/a3_probe_apk.json').read_text(encoding='utf-8'))
    adb('install', '-r', probe['apk'])
    imes = adb('shell', 'ime', 'list', '-s').splitlines()
    keyboard = next(i.strip() for i in imes if 'latin' in i.lower())
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
        '--ez',
        'nte_a3_cause',
        'true',
    )
    for _ in range(40):
        time.sleep(1)
        try:
            state()
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
        choose(label, key)
    s = fresh()
    tap(s['next'], s)
    s = fresh()
    tap(s['next'], s)
    s = fresh()
    assert s['step'] == 2
    rect, s = reach(
        lambda s: s['inputs']['y:CritDamagePP']['rect'], lambda s: s['page_scroll']
    )
    tap(rect, s)
    time.sleep(1)
    s, _ = record('h01_bottom_before')
    assert not s['inputs']['y:CritDamagePP']['focus'], (
        'Pre-fix blocked field unexpectedly focused'
    )
    tap(s['back'], s)
    s = fresh()
    assert s['step'] == 1
    for key, value, name in [
        ('current:UniversalPP', '12', 'h02_A'),
        ('current:OtherPP', '34', 'h02_B'),
        ('current:ElementPP', '56', 'h02_C'),
    ]:
        field(key, value, name)
    result = {
        'status': 'PRE_FIX_TRACE_RECORDED_REQUIRES_CAUSAL_REVIEW',
        'apk_commit': probe['metadata']['commit'],
    }
except Exception:
    result = {
        'status': 'HARNESS_OR_CAUSE_FAILURE_REVIEW_REQUIRED',
        'stacktrace': traceback.format_exc(),
    }
finally:
    logs = adb('logcat', '-d')
    (out / 'logcat.txt').write_text(logs, encoding='utf-8', newline='\n')
    events = [
        json.loads(line.split('NTE_A3_EVENT=', 1)[1])
        for line in logs.splitlines()
        if 'NTE_A3_EVENT=' in line
    ]
    for name, value in [
        ('events.json', events),
        ('timeline.json', timeline),
        ('result.json', result),
    ]:
        (out / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2),
            encoding='utf-8',
            newline='\n',
        )
assert result['status'] == 'PRE_FIX_TRACE_RECORDED_REQUIRES_CAUSAL_REVIEW', result
