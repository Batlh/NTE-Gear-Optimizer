"""Wait for a native probe artifact and verify its staged runtime hashes."""

import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time
import zipfile

assert os.environ.get('GITHUB_ACTIONS') == 'true'
repo = 'Batlh/NTE-Gear-Optimizer'
artifact_name = sys.argv[1] if len(sys.argv) > 1 else 'android-emulator-only-apk'
expected_probe = artifact_name == 'android-emulator-only-apk'
out = Path('build/a3_download')
out.mkdir(parents=True, exist_ok=True)
seen = set()
for attempt in range(50):
    listing = json.loads(
        subprocess.check_output(
            [
                'gh',
                'api',
                f'repos/{repo}/actions/artifacts?name={artifact_name}&per_page=20',
            ]
        )
    )
    for item in listing['artifacts']:
        if item['id'] in seen or item['expired']:
            continue
        if item['workflow_run']['head_branch'] != 'v029-phase2a':
            continue
        seen.add(item['id'])
        target = out / str(item['id'])
        subprocess.run(
            [
                'gh',
                'run',
                'download',
                str(item['workflow_run']['id']),
                '--repo',
                repo,
                '--name',
                item['name'],
                '--dir',
                str(target),
            ],
            check=True,
        )
        packages = list(target.rglob('*.apk'))
        if not packages:
            print(
                'Artifact contains no APK; native build failure evidence only:',
                item['id'],
            )
            continue
        assert len(packages) == 1
        apk = packages[0]
        with zipfile.ZipFile(apk) as z:
            with tarfile.open(
                fileobj=io.BytesIO(z.read('assets/private.tar')), mode='r:*'
            ) as t:
                metadata = json.load(t.extractfile('BUILD_METADATA.json'))

        def staged(p):
            return not any(
                '_REV_' in part or '_INTERMEDIATE_' in part or part == '__pycache__'
                for part in p.parts
            ) and p.suffix not in ('.pyc', '.ico', '.svg')

        expected = {
            p.relative_to('src').as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for package in ['nte_gear_optimizer', 'nte_gear_optimizer_app']
            for p in (Path('src') / package).rglob('*')
            if p.is_file() and staged(p)
        }
        for name in ['main.py', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'HANDYTEST_2A.md']:
            expected[name] = hashlib.sha256(Path(name).read_bytes()).hexdigest()
        expected['DATA_SOURCES.md'] = hashlib.sha256(
            Path('data/SOURCES.md').read_bytes()
        ).hexdigest()
        for p in Path('third_party_licenses').rglob('*'):
            if p.is_file() and staged(p):
                expected[p.as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
        actual = metadata['files']
        differences = sorted(
            name
            for name in expected.keys() | actual.keys()
            if expected.get(name) != actual.get(name)
        )
        build_names = (
            subprocess.check_output(
                [
                    'git',
                    'ls-files',
                    'buildozer.spec',
                    'requirements-android.txt',
                    'android',
                    'build_recipes',
                    'tools/configure_android_ci.py',
                    'tools/stage_android.py',
                    'tools/sign_android.py',
                ]
            )
            .decode('utf-8')
            .splitlines()
        )
        expected_build = {
            name: hashlib.sha256((Path(name)).read_bytes()).hexdigest()
            for name in build_names
        }
        if metadata.get('build_inputs') != expected_build:
            differences.append('native build-input manifest')
        if differences:
            print('Waiting for matching runtime; older artifact', item['id'])
            continue
        assert metadata['emulator_test_only'] is expected_probe
        Path('build/a3_probe_apk.json').write_text(
            json.dumps(
                {
                    'apk': str(apk),
                    'metadata': metadata,
                    'artifact': item,
                    'test_driver_commit': os.environ['GITHUB_SHA'],
                },
                indent=2,
            ),
            encoding='utf-8',
            newline='\n',
        )
        print('Matching native probe artifact', item['id'], metadata['commit'])
        raise SystemExit(0)
    time.sleep(30)
raise SystemExit(
    'No native artifact with byte-identical runtime sources; no touch test performed'
)
