"""Retain the actual already-resolved Android runtime dependency graph."""

import os
from pathlib import Path
import subprocess

assert os.environ.get('GITHUB_ACTIONS') == 'true'
abi = os.environ['NTE_ANDROID_ABI']
root = Path(__file__).resolve().parents[1]
wrappers = list(
    (root / f'.buildozer/android/platform/build-{abi}/dists').glob('*/gradlew')
)
assert len(wrappers) == 1, wrappers
wrapper = wrappers[0].resolve()
result = subprocess.run(
    [
        'bash',
        str(wrapper),
        '--offline',
        'dependencies',
        '--configuration',
        'debugRuntimeClasspath',
    ],
    cwd=wrapper.parent,
    capture_output=True,
    text=True,
    encoding='utf-8',
    errors='replace',
)
path = root / 'build/android_runtime_dependencies.txt'
with path.open('x', encoding='utf-8', newline='\n') as output:
    output.write(result.stdout + '\n' + result.stderr)
assert result.returncode == 0 and ' FAILED' not in result.stdout
assert 'androidx.core:core:1.15.0' in result.stdout
print('Actual Android runtime graph recorded without resolving new dependencies')
