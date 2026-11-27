"""Real adb input; inspect pre-fix H01 and keyboard focus/IME sequence."""

import json
import os
from pathlib import Path
import subprocess
import time
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from nte_gear_optimizer_app.probe_protocol import decode_probe

from android_ime_state import read_ime_state

assert os.environ.get('GITHUB_ACTIONS') == 'true'
out = Path('build/a3_android_fields')
out.mkdir(parents=True, exist_ok=False)
timeline = []
started = time.monotonic()


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
    return decode_probe(app_logs(6000))


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
    (out / (name + '_windows.txt')).write_text(
        adb('shell', 'dumpsys', 'window', 'windows'), encoding='utf-8', newline='\n'
    )
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


def collect_private_debug():
    # Read only the tested app's own diagnostic files. Keep the actual
    # caught JNI cause even when share/Downloads is the operation failing.
    target = out / 'private_debug'
    target.mkdir(exist_ok=True)
    package = 'io.github.batlh.nte_gear_optimizer'
    for directory in ['files/nte_debug/logs', 'cache/debug_reports']:
        listing = subprocess.run(
            ['adb', 'shell', 'run-as', package, 'ls', directory],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
        )
        if listing.returncode:
            continue
        for name in listing.stdout.splitlines():
            name = name.strip()
            allowed = name in {
                'events_0.jsonl',
                'events_1.jsonl',
                'events_2.jsonl',
            } or (
                name.startswith('NTE_Debugbericht_')
                and name.endswith('.txt')
                and '/' not in name
                and chr(92) not in name
            )
            if not allowed:
                continue
            result = subprocess.run(
                ['adb', 'exec-out', 'run-as', package, 'cat', directory + '/' + name],
                capture_output=True,
            )
            if result.returncode == 0:
                (target / name).write_bytes(result.stdout)
