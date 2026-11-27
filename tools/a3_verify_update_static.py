"""Static comparison of the two original arm64 APKs; no emulator claim."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from sign_android import certificate_metadata

assert os.environ.get('GITHUB_ACTIONS') == 'true'
out = Path('build/a3_update_static')
out.mkdir(parents=True, exist_ok=False)
sdk = Path(os.environ.get('ANDROID_HOME') or os.environ['ANDROID_SDK_ROOT'])
versions = [
    p for p in (sdk / 'build-tools').iterdir() if re.fullmatch(r'\d+\.\d+\.\d+', p.name)
]
tools = max(versions, key=lambda p: tuple(map(int, p.name.split('.'))))
expected = 'B153E792F3831DD58B17C62427CFC225732D534189F767323C9920A68B10B285'
baseline = next(Path('build/a3_baseline_apk').rglob('*.apk'))
candidate = Path(
    json.loads(Path('build/a3_probe_apk.json').read_text(encoding='utf-8'))['apk']
)
assert (
    hashlib.sha256(baseline.read_bytes()).hexdigest().upper()
    == '4CD54A10556891CF73478F7A1EE0462CF101DD1DFC65BA16B7A624EB1BB5D056'
)
rows = []
for role, apk in [('baseline_2a2', baseline), ('candidate_2a3', candidate)]:
    certificate = subprocess.check_output(
        [str(tools / 'apksigner'), 'verify', '--print-certs', str(apk)], text=True
    )
    # Reuse the signing job's parser: current apksigner labels schemes
    # V2/V3, older tools use Signer #1. One consistent public certificate
    # is required across all schemes; disagreement still fails closed.
    owner, fingerprint = certificate_metadata(certificate)
    assert fingerprint == expected
    badging = subprocess.check_output(
        [str(tools / 'aapt2'), 'dump', 'badging', str(apk)], text=True
    )
    package_line = next(
        line for line in badging.splitlines() if line.startswith('package:')
    )
    package = re.search(r"name='([^']+)'", package_line).group(1)
    version = int(re.search(r"versionCode='(\d+)'", package_line).group(1))
    assert package == 'io.github.batlh.nte_gear_optimizer'
    arches = re.search(r'^native-code: (.+)$', badging, re.MULTILINE).group(1)
    assert 'arm64-v8a' in arches
    permissions = re.findall(r"^uses-permission: name='([^']+)'", badging, re.MULTILINE)
    rows.append(
        {
            'role': role,
            'sha256': hashlib.sha256(apk.read_bytes()).hexdigest().upper(),
            'package': package,
            'version_code': version,
            'certificate_owner': owner,
            'certificate_sha256': fingerprint,
            'native_code': arches,
            'permissions': permissions,
        }
    )
assert rows[0]['version_code'] == 1002601
assert rows[1]['version_code'] > 1002601
assert not (set(rows[1]['permissions']) - set(rows[0]['permissions'])) & {
    'android.permission.INTERNET',
    'android.permission.READ_EXTERNAL_STORAGE',
    'android.permission.WRITE_EXTERNAL_STORAGE',
    'android.permission.MANAGE_EXTERNAL_STORAGE',
}
report = {
    'status': 'PASS_STATIC_COMPATIBILITY',
    'apksigner': 'verify --print-certs',
    'aapt2': 'dump badging',
    'build_tools_version': tools.name,
    'apks': rows,
    'emulator_update': 'UNVERIFIED_ABI_LIMIT',
    'real_update': 'PENDING_USER_SAMSUNG_AFTER_REVIEW',
    'x86_counter_build': 'NOT_AUTHORIZED_NOT_PERFORMED',
}
(out / 'result.json').write_text(
    json.dumps(report, indent=2), encoding='utf-8', newline='\n'
)
print(json.dumps(report, indent=2))
