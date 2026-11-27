"""Wait for a native probe artifact and verify its staged runtime hashes."""

import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import time
import zipfile

assert os.environ.get('GITHUB_ACTIONS') == 'true'
repo = 'Batlh/NTE-Gear-Optimizer'
out = Path('build/a3_download')
out.mkdir(parents=True, exist_ok=True)
seen = set()
for attempt in range(50):
    listing = json.loads(
        subprocess.check_output(
            [
                'gh',
                'api',
                f'repos/{repo}/actions/artifacts?name=android-emulator-only-apk&per_page=20',
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
        apk = next(target.rglob('*.apk'))
        with zipfile.ZipFile(apk) as z:
            with tarfile.open(
                fileobj=io.BytesIO(z.read('assets/private.tar')), mode='r:*'
            ) as t:
                metadata = json.load(t.extractfile('BUILD_METADATA.json'))
        differences = [
            name
            for name, digest in metadata['files'].items()
            if name.startswith(('nte_gear_optimizer/', 'nte_gear_optimizer_app/'))
            and hashlib.sha256((Path('src') / name).read_bytes()).hexdigest() != digest
        ]
        if differences:
            print('Waiting for matching runtime; older artifact', item['id'])
            continue
        assert metadata['emulator_test_only'] is True
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
