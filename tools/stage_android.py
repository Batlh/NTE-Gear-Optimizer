"""Stage only application inputs; no build-tree edits or imported user data."""

from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
target = root / 'build/android_source'
target.mkdir(parents=True, exist_ok=False)


def ignored(directory, names):
    return [
        n
        for n in names
        if '_REV_' in n
        or '_INTERMEDIATE_' in n
        or n == '__pycache__'
        or n.endswith(('.pyc', '.ico', '.svg'))
    ]


for package in ('nte_gear_optimizer', 'nte_gear_optimizer_app'):
    shutil.copytree(root / 'src' / package, target / package, ignore=ignored)
for name in ('main.py', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'HANDYTEST_2A.md'):
    shutil.copyfile(root / name, target / name)
shutil.copytree(root / 'third_party_licenses', target / 'third_party_licenses')
shutil.copyfile(root / 'data/SOURCES.md', target / 'DATA_SOURCES.md')

import json, subprocess, hashlib

info = {
    'emulator_test_only': __import__('os').environ.get('NTE_ANDROID_ABI') == 'x86_64',
    'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip(),
    'files': {
        p.relative_to(target).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in target.rglob('*')
        if p.is_file()
    },
}
with (target / 'BUILD_METADATA.json').open(
    'x', encoding='utf-8', newline='\n'
) as stream:
    json.dump(info, stream, indent=2)
