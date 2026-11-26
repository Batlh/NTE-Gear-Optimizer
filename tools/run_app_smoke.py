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
    'KIVY_WINDOW': 'sdl2',
    'KIVY_AUDIO': 'mock',
    'KIVY_HOME': str(out / 'kivy_home'),
    'LIBGL_ALWAYS_SOFTWARE': '1',
}
command = [str(Path(args.exe).resolve())] if args.exe else [sys.executable, 'main.py']
try:
    result = subprocess.run(
        command,
        env=env,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=120,
    )
except subprocess.TimeoutExpired as error:
    if sys.platform == 'win32':
        from PIL import ImageGrab

        ImageGrab.grab().save(out / 'timeout_desktop.png')
    raise
with (out / 'app_stdout.txt').open('x', encoding='utf-8', newline='\n') as target:
    target.write(result.stdout)
with (out / 'app_stderr.txt').open('x', encoding='utf-8', newline='\n') as target:
    target.write(result.stderr)
assert result.returncode == 0, (
    result.returncode,
    result.stderr[-4000:],
    result.stdout[-4000:],
)
report = json.loads((out / 'smoke_result.json').read_text(encoding='utf-8'))
assert report['result']['engine']['VerdictRatio'] == '1.100000000'
assert report['result']['engine']['Verdict'] == 'BETTER'
assert report['result']['engine']['Deltas']['ScaleDirect'] == '10'
assert report['frozen'] == bool(args.exe)
followup = json.loads((out / 'followup_checks.json').read_text(encoding='utf-8'))
assert all(value == 'PASS' or value is True for value in followup.values()), followup
assert (
    len(list(out.glob('details_expanded*.png'))) == 1
    and len(list(out.glob('input_help*.png'))) == 1
)
screenshots = list(out.glob('step_*.png'))
assert len(screenshots) == 4
from PIL import Image, ImageStat

for screenshot in (
    screenshots
    + list(out.glob('details_expanded*.png'))
    + list(out.glob('input_help*.png'))
):
    with Image.open(screenshot) as image:
        # Exclude window chrome: a title bar over a black client is not proof.
        client = image.convert('RGB').crop(
            (20, 80, image.width - 20, image.height - 60)
        )
        assert max(ImageStat.Stat(client).stddev) > 10, ('Blank screenshot', screenshot)
        assert len(client.getcolors(1000000) or []) > 50, (
            'No rendered controls',
            screenshot,
        )

with (out / 'files.json').open('x', encoding='utf-8', newline='\n') as target:
    json.dump(
        {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in out.iterdir()
            if p.name != 'files.json' and p.is_file()
        },
        target,
        indent=2,
    )
print('Four guided screens exercised; result, input callbacks and screenshots PASS')
