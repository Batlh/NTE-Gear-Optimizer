"""CI-only same-emulator ABBA comparison of two unchanged original probe APKs."""

import hashlib, io, json, os, platform, subprocess, sys, tarfile, time, zipfile, statistics
from pathlib import Path

assert os.environ.get('GITHUB_ACTIONS') == 'true' and sys.platform == 'linux'
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/a4_controlled'
PACKAGE = 'io.github.batlh.nte_gear_optimizer'
SPECS = {
    'A': {
        'run': 46070672437,
        'artifact_id': 15233063366,
        'commit': '5f894cfb623773aee840db4764bb0edf742f1229',
        'sha256': '67B081FAEF06A8AA8F5BAE98894BE5FA35BC1C7CBE500B5346773848A173F83C',
    },
    'B': {
        'run': 46081630384,
        'artifact_id': 15237254694,
        'commit': '2596cae9264a0dfa0900e9e74aa889eb8933dc3d',
        'sha256': 'A9E0C24155A3E5C37166F53813B7CD52E76349272D4387951403245FA2CEA267',
    },
}


def text(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')


def prepare():
    OUT.mkdir(parents=True, exist_ok=False)
    rows = {}
    for label, spec in SPECS.items():
        target = OUT / ('original_' + label)
        subprocess.run(
            [
                'gh',
                'run',
                'download',
                str(spec['run']),
                '--repo',
                'Batlh/NTE-Gear-Optimizer',
                '--name',
                'android-emulator-only-apk',
                '--dir',
                str(target),
            ],
            check=True,
        )
        packages = list(target.rglob('*.apk'))
        assert len(packages) == 1
        apk = packages[0].resolve()
        digest = hashlib.file_digest(apk.open('rb'), 'sha256').hexdigest().upper()
        assert digest == spec['sha256'], label
        with zipfile.ZipFile(apk) as z:
            with tarfile.open(
                fileobj=io.BytesIO(z.read('assets/private.tar')), mode='r:*'
            ) as t:
                metadata = json.load(t.extractfile('BUILD_METADATA.json'))
        assert (
            metadata['commit'] == spec['commit']
            and metadata['emulator_test_only'] is True
        )
        record = json.loads(
            next(target.rglob('android_artifact.json')).read_text(encoding='utf-8')
        )
        assert record['abi'] == 'x86_64' and record['package'] == PACKAGE
        assert record['debug_only'] and record['emulator_only_debug_signature_verified']
        rows[label] = {
            'apk': str(apk),
            'metadata': metadata,
            'original_spec': spec,
            'test_driver_commit': os.environ['GITHUB_SHA'],
        }

    def core(row):
        return {
            k: v
            for k, v in row['metadata']['files'].items()
            if k.startswith('nte_gear_optimizer/')
            or k == 'nte_gear_optimizer_app/viewmodel.py'
            or '/assets/icons/' in k
            or k.endswith('/assets/catalog.json')
        }

    assert core(rows['A']) == core(rows['B'])
    assert (
        rows['A']['metadata']['build_inputs'] == rows['B']['metadata']['build_inputs']
    )
    text(
        OUT / 'prepared.json',
        {
            'order': ['A1', 'B1', 'B2', 'A2'],
            'probes': rows,
            'scope': 'Original x86-only diagnostic APKs, not ARM user/update packages. No counter-build, re-signing, new key or modified APK.',
        },
    )
    print('Two original immutable probe APKs and identical core/build inputs verified.')


def adb(*args):
    return subprocess.check_output(['adb', *args], text=True, encoding='utf-8').strip()


def run():
    assert (
        adb('get-serialno').startswith('emulator-')
        and adb('shell', 'getprop', 'ro.kernel.qemu') == '1'
    )
    plan = json.loads((OUT / 'prepared.json').read_text(encoding='utf-8'))
    host = {
        'platform': platform.platform(),
        'cpu_count': os.cpu_count(),
        'model_name': next(
            (
                line.split(':', 1)[1].strip()
                for line in Path('/proc/cpuinfo').read_text().splitlines()
                if line.startswith('model name')
            ),
            None,
        ),
        'serial': adb('get-serialno'),
        'device': adb('shell', 'getprop', 'ro.product.model'),
        'size': adb('shell', 'wm', 'size'),
        'density': adb('shell', 'wm', 'density'),
    }
    text(OUT / 'host.json', host)
    rows = []
    for label in plan['order']:
        probe = plan['probes'][label[0]]
        assert (
            hashlib.file_digest(Path(probe['apk']).open('rb'), 'sha256')
            .hexdigest()
            .upper()
            == probe['original_spec']['sha256']
        )
        # Different original CI debug certificates cannot update each other.
        # Reset ONLY this disposable emulator's synthetic test package. All
        # prior stage logs/results remain in independent host directories.
        installed = adb('shell', 'pm', 'list', 'packages', PACKAGE).splitlines()
        if 'package:' + PACKAGE in installed:
            assert adb('uninstall', PACKAGE) == 'Success'
        stage = OUT / label
        (stage / 'build').mkdir(parents=True, exist_ok=False)
        text(stage / 'build/a3_probe_apk.json', probe)
        started = time.monotonic()
        process = subprocess.run(
            [sys.executable, str(ROOT / 'tools/a4_performance_android.py')], cwd=stage
        )
        result = json.loads(
            (stage / 'build/a4_performance_android/result.json').read_text(
                encoding='utf-8'
            )
        )
        assert process.returncode == 0 and result['status'] == 'MEASURED', label
        assert result['source_commit'] == probe['original_spec']['commit']
        gs = [
            g
            for block in result['logging_blocks']
            if block['logging']
            for g in block['gestures']
        ]
        row = {
            'label': label,
            'source_commit': result['source_commit'],
            'apk_sha256': probe['original_spec']['sha256'],
            'elapsed_seconds': time.monotonic() - started,
            'gesture_count_on': len(gs),
            'fps_median_on': statistics.median(g['fps'] for g in gs),
            'frame_interval_median_on': statistics.median(
                g['frame_interval_median_ms'] for g in gs
            ),
            'first_drag_median_on': statistics.median(
                g['first_drag_to_visible_movement_ms'] for g in gs
            ),
            'idle_flips': result['idle_flips_in_two_seconds'],
        }
        rows.append(row)
        text(stage / 'summary.json', row)
        print('Controlled stage', label, 'MEASURED', flush=True)
    med = {
        kind: statistics.median(
            r['fps_median_on'] for r in rows if r['label'][0] == kind
        )
        for kind in ['A', 'B']
    }
    text(
        OUT / 'controlled_result.json',
        {
            'status': 'MEASURED',
            'scope': 'Same host and same running emulator; original immutable APKs; predetermined A-B-B-A order; fresh synthetic installs because CI debug certificates differ. Not an update test and not physical Samsung proof.',
            'rows': rows,
            'stage_median_fps': med,
            'B_vs_A_median_fps_change_percent': 100 * (med['B'] / med['A'] - 1),
            'driver_sha256': hashlib.sha256(
                (ROOT / 'tools/a4_performance_android.py').read_bytes()
            ).hexdigest(),
            'host': host,
        },
    )


if __name__ == '__main__':
    if sys.argv[1] == 'prepare':
        prepare()
    elif sys.argv[1] == 'run':
        run()
    else:
        raise SystemExit('Expected prepare or run')
