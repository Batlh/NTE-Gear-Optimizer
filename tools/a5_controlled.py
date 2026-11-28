"""Immutable H01/current same-host ABBA, real OS input, CI only."""

import hashlib, json, os, subprocess, sys
from pathlib import Path

assert os.environ.get('GITHUB_ACTIONS') == 'true'
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/a5_controlled'
BASE = '52ade37e9e00e26802c487fb6e772825ae2ffe1f'


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)


def prepare():
    OUT.mkdir(parents=True, exist_ok=False)
    target = OUT / 'original_h01'
    subprocess.run(
        [
            'gh',
            'run',
            'download',
            '46126308441',
            '--repo',
            'Batlh/NTE-Gear-Optimizer',
            '--name',
            'android-emulator-only-apk',
            '--dir',
            str(target),
        ],
        check=True,
    )
    apk = list(target.rglob('*.apk'))
    assert len(apk) == 1
    digest = hashlib.sha256(apk[0].read_bytes()).hexdigest().upper()
    assert digest == '60C11DBA0516BCFF1ECAEAEB232A4AADB978DDF51BA16FD2C47CBD1B4BDCC0E8'
    # Both comparison APKs are immutable: H01 and the display-read fix only.
    # Do not silently compare against whichever later runtime the driver uses.
    target_b = OUT / 'display_read_fix'
    subprocess.run(
        [
            'gh',
            'run',
            'download',
            '46140920049',
            '--repo',
            'Batlh/NTE-Gear-Optimizer',
            '--name',
            'android-emulator-only-apk',
            '--dir',
            str(target_b),
        ],
        check=True,
    )
    apks_b = list(target_b.rglob('*.apk'))
    assert len(apks_b) == 1
    digest_b = hashlib.sha256(apks_b[0].read_bytes()).hexdigest().upper()
    assert (
        digest_b == 'AC2243244B8CB7FDB5D6B05A177E44995968159A977C8777C3F6F6A677B28EED'
    )
    current = {
        'apk': str(apks_b[0].resolve()),
        'sha256': digest_b,
        'commit': '3ac7b013c578664f349047286dd0567a2e0f1557',
    }
    save(
        OUT / 'prepared.json',
        {
            'A': {
                'apk': str(apk[0].resolve()),
                'sha256': digest,
                'commit': '8f9709f7e35ab1524cd54ec2929d38a188e41c9b',
            },
            'B': current,
        },
    )


def run_android():
    assert sys.platform == 'linux'
    plan = json.loads((OUT / 'prepared.json').read_text(encoding='utf-8'))
    serial = subprocess.check_output(['adb', 'get-serialno'], text=True).strip()
    assert serial.startswith('emulator-')
    results = []
    for label in ['A1', 'B1', 'B2', 'A2']:
        probe = plan[label[0]]
        packages = subprocess.check_output(
            [
                'adb',
                'shell',
                'pm',
                'list',
                'packages',
                'io.github.batlh.nte_gear_optimizer',
            ],
            text=True,
        )
        if 'package:io.github.batlh.nte_gear_optimizer' in packages:
            # Only disposable CI synthetic app, never a user's installed app.
            subprocess.run(
                ['adb', 'uninstall', 'io.github.batlh.nte_gear_optimizer'], check=True
            )
        stage = OUT / label
        (stage / 'build').mkdir(parents=True, exist_ok=False)
        save(stage / 'build/a3_probe_apk.json', probe)
        env = {
            **os.environ,
            'NTE_A5_COMPARE': '1',
            'NTE_A5_BASELINE': '1' if label[0] == 'A' else '0',
        }
        p = subprocess.run(
            [sys.executable, str(ROOT / 'tools/a5_profile_android.py')],
            cwd=stage,
            env=env,
        )
        r = json.loads(
            (stage / 'build/a5_profile_android/result.json').read_text(encoding='utf-8')
        )
        results.append({'stage': label, 'result': r})
        save(OUT / ('results_' + label + '.json'), results[-1])
        assert p.returncode == 0 and r['status'] == 'MEASURED', label
    save(
        OUT / 'result.json',
        {
            'status': 'MEASURED',
            'order': 'ABBA',
            'results': results,
            'serial': serial,
            'scope': 'Same emulator; original H01/current immutable APKs; profiling off, journal on. Not a Samsung/update proof.',
        },
    )


def run_windows():
    assert sys.platform == 'win32'
    OUT.mkdir(parents=True, exist_ok=False)
    subprocess.run(['git', 'fetch', '--no-tags', 'origin', BASE], check=True)
    results = []
    for label in ['A1', 'B1', 'B2', 'A2']:
        base = BASE if label[0] == 'A' else os.environ['GITHUB_SHA']
        stage = OUT / label
        subprocess.run(
            ['git', 'worktree', 'add', '--detach', str(stage), base], check=True
        )
        driver = stage / 'tools/a5_profile_windows.py'
        driver.write_bytes((ROOT / 'tools/a5_profile_windows.py').read_bytes())
        p = subprocess.run(
            [sys.executable, str(driver)],
            cwd=stage,
            env={**os.environ, 'NTE_A5_COMPARE': '1'},
        )
        r = json.loads(
            (stage / 'build/a5_profile_windows/result.json').read_text(encoding='utf-8')
        )
        results.append({'stage': label, 'result': r})
        save(OUT / ('results_' + label + '.json'), results[-1])
        assert p.returncode == 0 and r['status'] == 'MEASURED', label
    save(
        OUT / 'result.json',
        {
            'status': 'MEASURED',
            'order': 'ABBA',
            'results': results,
            'scope': 'Same Windows runner; isolated original H01/current source snapshots; identical real OS mouse driver, profile off, journal on.',
        },
    )


if __name__ == '__main__':
    {'prepare': prepare, 'android': run_android, 'windows': run_windows}[sys.argv[1]]()
