"""Only the observation driver changes in the detached baseline CI tree."""

import os
from pathlib import Path
import subprocess
import sys

assert os.environ.get('GITHUB_ACTIONS') == 'true' and sys.platform == 'win32'
root = Path(__file__).resolve().parents[1]
stage = sys.argv[1]
assert stage in ('baseline', 'current')
if stage == 'current':
    command = [sys.executable, 'tools/a4_performance_windows.py']
    subprocess.run(command, cwd=root, check=True)
else:
    base = '493a99f395a037be09428335c2f15073bfbb34b7'
    target = root / 'build/a4_frozen_baseline'
    assert not target.exists()
    subprocess.run(['git', 'fetch', '--no-tags', 'origin', base], check=True)
    subprocess.run(
        ['git', 'worktree', 'add', '--detach', str(target), base], check=True
    )
    # Identical current input/observation driver; no runtime file is changed.
    driver = 'tools/a4_performance_windows.py'
    (target / driver).write_bytes((root / driver).read_bytes())
    changed = subprocess.check_output(
        ['git', 'diff', '--name-only', 'HEAD'], cwd=target, text=True
    ).splitlines()
    assert changed == [driver], changed
    env = {**os.environ, 'NTE_A4_FROZEN_BASELINE': '1'}
    subprocess.run([sys.executable, driver], cwd=target, env=env, check=True)
