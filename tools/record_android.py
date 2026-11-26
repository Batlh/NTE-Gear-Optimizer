import hashlib, json, zipfile, subprocess
from pathlib import Path

apks = list(Path('bin').glob('*.apk'))
assert apks
result = {
    'files': {},
    'package': 'io.github.batlh.nte_gear_optimizer',
    'abi': 'arm64-v8a',
    'python': '3.14.2',
    'hostpython': '3.14.2',
    'kivy': '2.3.2',
    'debug_only': True,
}
for path in apks:
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        assert 'AndroidManifest.xml' in archive.namelist()
        assert any('lib/arm64-v8a/' in name for name in archive.namelist())
    result['files'][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
with Path('build/android_artifact.json').open(
    'x', encoding='utf-8', newline='\n'
) as target:
    json.dump(result, target, indent=2)
