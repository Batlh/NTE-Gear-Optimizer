"""Literal fixed-key APK update test, never uninstalling either application."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import traceback

assert os.environ.get('GITHUB_ACTIONS') == 'true'
out = Path('build/a3_update')
out.mkdir(parents=True, exist_ok=False)
package = 'io.github.batlh.nte_gear_optimizer'


def adb(*args):
    return subprocess.check_output(
        ['adb', *args], text=True, encoding='utf-8', errors='replace'
    )


def version():
    dump = adb('shell', 'dumpsys', 'package', package)
    values = re.findall(r'versionCode=(\d+)', dump)
    assert len(values) == 1, values
    return int(values[0])


def launch(name):
    adb('shell', 'am', 'force-stop', package)
    adb('logcat', '-c')
    adb('shell', 'am', 'start', '-n', package + '/org.kivy.android.PythonActivity')
    time.sleep(15)
    assert adb('shell', 'pidof', package).strip()
    log = adb('logcat', '-d')
    (out / (name + '_logcat.txt')).write_text(log, encoding='utf-8', newline='\n')
    assert 'FATAL EXCEPTION' not in log and 'Python for android ended' not in log, log[
        -6000:
    ]
    (out / (name + '.png')).write_bytes(
        subprocess.check_output(['adb', 'exec-out', 'screencap', '-p'])
    )


result = {'status': 'PENDING'}
try:
    baseline = next(Path('build/a3_baseline_apk').rglob('*.apk'))
    current = json.loads(Path('build/a3_probe_apk.json').read_text(encoding='utf-8'))
    candidate = Path(current['apk'])
    digest = hashlib.sha256(baseline.read_bytes()).hexdigest().upper()
    assert digest == '4CD54A10556891CF73478F7A1EE0462CF101DD1DFC65BA16B7A624EB1BB5D056'
    capabilities = {
        'abis': adb('shell', 'getprop', 'ro.product.cpu.abilist').strip(),
        'native_bridge': adb('shell', 'getprop', 'ro.dalvik.vm.native.bridge').strip(),
    }
    (out / 'emulator_abis.json').write_text(
        json.dumps(capabilities, indent=2), encoding='utf-8', newline='\n'
    )
    baseline_install = adb('install', '-r', str(baseline))
    assert 'Success' in baseline_install, baseline_install
    assert version() == 1002601
    launch('phase2a2_before_update')
    adb('shell', 'run-as', package, 'touch', 'files/a3_update_marker')
    install = adb('install', '-r', str(candidate))
    assert 'Success' in install, install
    assert version() > 1002601
    assert 'a3_update_marker' in adb(
        'shell', 'run-as', package, 'ls', 'files/a3_update_marker'
    )
    launch('phase2a3_after_update')
    result = {
        'status': 'PASS',
        'baseline_sha256': digest,
        'candidate_sha256': hashlib.sha256(candidate.read_bytes()).hexdigest().upper(),
        'before_version_code': 1002601,
        'after_version_code': version(),
        'private_marker_preserved': True,
        'install_command': 'adb install -r',
        'capabilities': capabilities,
    }
except Exception:
    result = {
        'status': 'FAIL_OR_ABI_UNVERIFIED_REQUIRES_REVIEW',
        'stacktrace': traceback.format_exc(),
    }
finally:
    (out / 'result.json').write_text(
        json.dumps(result, indent=2), encoding='utf-8', newline='\n'
    )
assert result['status'] == 'PASS', result
