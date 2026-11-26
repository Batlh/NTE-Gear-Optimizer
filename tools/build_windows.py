"""CI-only Windows onedir packaging with bundled notices and source metadata."""

import subprocess, sys, os, shutil, json, hashlib
from pathlib import Path

if os.environ.get('GITHUB_ACTIONS') != 'true' or sys.platform != 'win32':
    raise SystemExit('Windows CI only')
root = Path(__file__).resolve().parents[1]
subprocess.run(
    [
        sys.executable,
        '-m',
        'PyInstaller',
        '--noconfirm',
        '--clean',
        '--onedir',
        '--windowed',
        '--name',
        'NTEGearOptimizer',
        '--paths',
        'src',
        '--collect-data',
        'kivy',
        '--collect-binaries',
        'kivy',
        '--exclude-module',
        'kivy.garden',
        '--exclude-module',
        'kivy.tests',
        '--hidden-import',
        'kivy.core.window.window_sdl2',
        '--hidden-import',
        'kivy.core.text.text_sdl2',
        '--hidden-import',
        'kivy.core.image.img_sdl2',
        '--collect-submodules',
        'nte_gear_optimizer',
        '--add-data',
        str(root / 'src/nte_gear_optimizer_app/assets')
        + os.pathsep
        + 'nte_gear_optimizer_app/assets',
        'main.py',
    ],
    check=True,
)
bundle = root / 'dist/NTEGearOptimizer'
for name in ('LICENSE', 'THIRD_PARTY_NOTICES.md', 'HANDYTEST_2A.md'):
    shutil.copyfile(root / name, bundle / name)
shutil.copytree(root / 'third_party_licenses', bundle / 'third_party_licenses')
shutil.copyfile(root / 'data/SOURCES.md', bundle / 'DATA_SOURCES.md')
inventory = {
    p.relative_to(bundle).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in bundle.rglob('*')
    if p.is_file()
}
with (bundle / 'BUNDLE_FILES.json').open('x', encoding='utf-8', newline='\n') as target:
    json.dump(inventory, target, indent=2)
shutil.make_archive(
    str(root / 'dist/NTE_Gear_Optimizer_v029_Phase2A_Windows_Debug'),
    'zip',
    root / 'dist',
    'NTEGearOptimizer',
)
