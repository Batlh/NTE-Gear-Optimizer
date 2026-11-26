"""CI-only visible app exercise. Never launches on the user's workstation."""

import argparse, os, sys, subprocess, json, hashlib
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--output', required=True)
parser.add_argument('--exe')
args = parser.parse_args()
if os.environ.get('GITHUB_ACTIONS') != 'true':
    raise SystemExit('Visible app smoke is allowed only on the isolated CI runner')
out = Path(args.output).resolve()
out.mkdir(parents=True, exist_ok=False)
env = {
    **os.environ,
    'NTE_TEST_MODE': 'smoke',
    'NTE_TEST_OUTPUT': str(out),
    'KIVY_NO_ARGS': '1',
    'KIVY_NO_CONSOLELOG': '0',
    'KIVY_WINDOW': 'sdl2',
    'KIVY_AUDIO': 'mock',
}
command = [str(Path(args.exe).resolve())] if args.exe else [sys.executable, 'main.py']
result = subprocess.run(
    command,
    env=env,
    capture_output=True,
    text=True,
    encoding='utf-8',
    errors='replace',
    timeout=120,
)
with (out / 'app_stdout.txt').open('x', encoding='utf-8', newline='\n') as target:
    target.write(result.stdout)
with (out / 'app_stderr.txt').open('x', encoding='utf-8', newline='\n') as target:
    target.write(result.stderr)
assert result.returncode == 0, (result.returncode, result.stderr[-4000:])
report = json.loads((out / 'smoke_result.json').read_text(encoding='utf-8'))
assert report['result']['engine']['VerdictRatio'] == '1.100000000'
assert report['result']['engine']['Verdict'] == 'BETTER'
assert report['result']['engine']['Deltas']['ScaleDirect'] == '10'
assert report['frozen'] == bool(args.exe)
screenshots = list(out.glob('step_*.png'))
assert len(screenshots) == 4
with (out / 'files.json').open('x', encoding='utf-8', newline='\n') as target:
    json.dump(
        {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in out.iterdir()
            if p.name != 'files.json'
        },
        target,
        indent=2,
    )
print('Four guided screens exercised; result, input callbacks and screenshots PASS')
