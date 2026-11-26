"""Reproducible spec variant, before build; no manual build-tree edits."""

import os
from pathlib import Path

assert os.environ.get('GITHUB_ACTIONS') == 'true'
abi = os.environ['NTE_ANDROID_ABI']
assert abi in ('arm64-v8a', 'x86_64')
version = (
    1000000
    + int(os.environ['GITHUB_RUN_NUMBER']) * 100
    + int(os.environ['GITHUB_RUN_ATTEMPT'])
)
assert version < 2100000000
path = Path('buildozer.spec')
source = path.read_text(encoding='utf-8').replace(
    'android.archs = arm64-v8a', 'android.archs = ' + abi
)
source = source.replace(
    'version = 0.29.0', 'version = 0.29.0\nandroid.numeric_version = ' + str(version)
)
with path.open('w', encoding='utf-8', newline='\n') as stream:
    stream.write(source)
with Path(os.environ['GITHUB_ENV']).open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('NTE_VERSION_CODE=' + str(version) + '\n')
