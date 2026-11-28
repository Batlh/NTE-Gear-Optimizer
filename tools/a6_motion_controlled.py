"""Motion-allocation same-host ABBA+BAAB, real OS input, CI only."""

import hashlib, json, os, subprocess, sys, zipfile
from pathlib import Path

assert os.environ.get('GITHUB_ACTIONS') == 'true'
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/a6_motion_controlled'
BASE = 'cc292349234efd21b648afbbd6033143334886bf'


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)


def prepare():
    import io, tarfile, time

    OUT.mkdir(parents=True, exist_ok=False)
    # Current artifact is already payload-bound by a3_fetch_probe_apk.py.
    current = json.loads((ROOT / 'build/a3_probe_apk.json').read_text(encoding='utf-8'))
    current['apk'] = str(Path(current['apk']).resolve())
    current['sha256'] = (
        hashlib.sha256(Path(current['apk']).read_bytes()).hexdigest().upper()
    )
    target = OUT / 'baseline'
    for attempt in range(50):
        listing = json.loads(
            subprocess.check_output(
                [
                    'gh',
                    'api',
                    'repos/Batlh/NTE-Gear-Optimizer/actions/runs/46167714761/artifacts',
                ]
            )
        )
        artifact = next(
            (
                a
                for a in listing['artifacts']
                if a['name'] == 'android-emulator-only-apk'
            ),
            None,
        )
        if artifact:
            subprocess.run(
                [
                    'gh',
                    'run',
                    'download',
                    '46167714761',
                    '--repo',
                    'Batlh/NTE-Gear-Optimizer',
                    '--name',
                    artifact['name'],
                    '--dir',
                    str(target),
                ],
                check=True,
            )
            break
        time.sleep(30)
    else:
        raise AssertionError('Immutable baseline APK not available; no substitute')
    apks = list(target.rglob('*.apk'))
    assert len(apks) == 1
    apk = apks[0]
    with (
        zipfile.ZipFile(apk) as z,
        tarfile.open(
            fileobj=io.BytesIO(z.read('assets/private.tar')), mode='r:*'
        ) as tar,
    ):
        metadata = json.load(tar.extractfile('BUILD_METADATA.json'))
    assert metadata['commit'] == BASE and metadata['emulator_test_only'] is True
    subprocess.run(['git', 'fetch', '--no-tags', 'origin', BASE], check=True)
    source_tar = subprocess.check_output(['git', 'archive', '--format=tar', BASE])
    with tarfile.open(fileobj=io.BytesIO(source_tar), mode='r:') as source:

        def source_hash(name):
            path = (
                'src/' + name
                if name.startswith(('nte_gear_optimizer/', 'nte_gear_optimizer_app/'))
                else ('data/SOURCES.md' if name == 'DATA_SOURCES.md' else name)
            )
            stream = source.extractfile(path)
            assert stream is not None, path
            return hashlib.sha256(stream.read()).hexdigest()

        assert all(
            source_hash(name) == digest for name, digest in metadata['files'].items()
        )
        assert all(
            source_hash(name) == digest
            for name, digest in metadata['build_inputs'].items()
        )

    base = {
        'apk': str(apk.resolve()),
        'sha256': hashlib.sha256(apk.read_bytes()).hexdigest().upper(),
        'metadata': metadata,
        'artifact': artifact,
    }
    save(OUT / 'prepared.json', {'A': base, 'B': current})


def run_android():
    assert sys.platform == 'linux'
    plan = json.loads((OUT / 'prepared.json').read_text(encoding='utf-8'))
    serial = subprocess.check_output(['adb', 'get-serialno'], text=True).strip()
    assert serial.startswith('emulator-')
    results = []
    for label in ['A1', 'B1', 'B2', 'A2', 'B3', 'A3', 'A4', 'B4']:
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
            'NTE_A5_BASELINE': '0',
            'NTE_A6_PROFILE_COMPARE': '1',
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
            'order': 'ABBA+BAAB',
            'results': results,
            'serial': serial,
            'scope': 'Same emulator; immutable no-hover baseline/current motion-cache APKs; profiling on, journal on, GC BASE. Not a production FPS guarantee. Not a Samsung/update proof.',
        },
    )


def run_windows():
    assert sys.platform == 'win32'
    OUT.mkdir(parents=True, exist_ok=False)
    subprocess.run(['git', 'fetch', '--no-tags', 'origin', BASE], check=True)
    results = []
    for label in ['A1', 'B1', 'B2', 'A2', 'B3', 'A3', 'A4', 'B4']:
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
            env={**os.environ, 'NTE_A5_COMPARE': '1', 'NTE_A6_PROFILE_COMPARE': '1'},
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
            'order': 'ABBA+BAAB',
            'results': results,
            'scope': 'Same Windows runner; isolated no-hover baseline/current snapshots; identical real OS mouse driver, profiling on, GC BASE.',
        },
    )


if __name__ == '__main__':
    {'prepare': prepare, 'android': run_android, 'windows': run_windows}[sys.argv[1]]()
