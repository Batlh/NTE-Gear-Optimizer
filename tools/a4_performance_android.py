"""Measure native adb gestures; no model, focus or scroll injection."""

import json
import subprocess
import time
import traceback
import a3_android_common as ui

out = ui.Path('build/a4_performance_android')
out.mkdir(parents=True, exist_ok=False)
failure = None
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
    )
    for _ in range(40):
        time.sleep(1)
        try:
            s = ui.state()
            break
        except AssertionError:
            pass
    else:
        raise AssertionError('App did not produce a native UI observation')
    for _ in range(4):
        ui.swipe(s['page_scroll'], s, reverse=False)
        time.sleep(1.2)
        s = ui.fresh()
        ui.swipe(s['page_scroll'], s, reverse=True)
        time.sleep(1.2)
        s = ui.fresh()
    time.sleep(1)
except Exception:
    failure = traceback.format_exc()
finally:
    rows = []
    collection_errors = []
    (out / 'scenario_failure.txt').write_text(
        failure or 'No scenario exception', encoding='utf-8', newline='\n'
    )
    (out / 'app_logcat.txt').write_text(ui.app_logs(), encoding='utf-8', newline='\n')
    for name in ['events_2.jsonl', 'events_1.jsonl', 'events_0.jsonl']:
        p = subprocess.run(
            [
                'adb',
                'exec-out',
                'run-as',
                'io.github.batlh.nte_gear_optimizer',
                'cat',
                'files/nte_debug/logs/' + name,
            ],
            capture_output=True,
        )
        (out / (name + '.raw.txt')).write_bytes(p.stdout)
        for line in p.stdout.decode('utf-8', errors='replace').splitlines():
            try:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError('Expected journal record')
                rows.append(row)
            except ValueError:
                collection_errors.append(
                    {'file': name, 'line': line[:200], 'returncode': p.returncode}
                )
    gestures = [r for r in rows if r.get('event') == 'scroll_gesture_metrics']
    measured = [r for r in gestures if r.get('status') == 'MEASURED_GL_FLIP_PROXY']
    result = {
        'status': 'MEASURED' if not failure and len(measured) >= 6 else 'FAIL',
        'failure': failure,
        'collection_errors': collection_errors,
        'source_commit': probe['metadata']['commit']
        if 'metadata' in probe
        else probe.get('commit'),
        'platform': 'android_emulator',
        'gestures': gestures,
        'apk_probe': probe,
        'scope': 'Isolated Android13 emulator; GL flip proxy, not Samsung physical device.',
    }
    with (out / 'result.json').open('x', encoding='utf-8', newline='\n') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    (out / 'after_gestures.png').write_bytes(
        subprocess.check_output(['adb', 'exec-out', 'screencap', '-p'])
    )
    (out / 'app_logcat.txt').write_text(ui.app_logs(), encoding='utf-8', newline='\n')
assert result['status'] == 'MEASURED', result
