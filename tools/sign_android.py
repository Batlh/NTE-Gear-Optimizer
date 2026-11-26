"""Sign only the own-branch CI APK; never expose password/key material."""

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


def single_alias(listing):
    aliases = re.findall(r'^Alias name: (.+)$', listing, re.M)
    if len(aliases) != 1 or listing.count('Entry type: PrivateKeyEntry') != 1:
        raise ValueError('STOP: keystore must contain exactly one private-key entry')
    return aliases[0].strip()


def checked(command):
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode:
        # Keytool/signer output is deliberately NOT echoed on failure.
        raise RuntimeError(
            'STOP: signing/password/keystore verification failed; no secret output retained'
        )
    return completed.stdout


def certificate_metadata(output):
    # Build-tools uses scheme-labelled V2/V3 Signer lines; older versions
    # use Signer #1. Require one consistent certificate across schemes.
    owners = set()
    fingerprints = set()
    for line in output.splitlines():
        if 'Source Stamp' in line or 'SourceStamp' in line:
            continue
        if ' certificate DN: ' in line:
            owners.add(line.split(' certificate DN: ', 1)[1].strip())
        if ' certificate SHA-256 digest: ' in line:
            fingerprints.add(
                line.split(' certificate SHA-256 digest: ', 1)[1].strip().upper()
            )
    if len(owners) != 1 or len(fingerprints) != 1:
        raise ValueError(
            'STOP: certificate output missing or inconsistent across signature schemes'
        )
    owner = owners.pop()
    fingerprint = fingerprints.pop()
    if 'Android Debug' in owner or not re.fullmatch('[0-9A-F]{64}', fingerprint):
        raise ValueError('STOP: non-release or invalid public signing certificate')
    return owner, fingerprint


def main():
    assert os.environ.get('GITHUB_ACTIONS') == 'true'
    assert os.environ.get('GITHUB_EVENT_NAME') == 'push'
    assert os.environ.get('GITHUB_REPOSITORY') == 'Batlh/NTE-Gear-Optimizer'
    assert os.environ.get('GITHUB_REF') == 'refs/heads/v029-phase2a'
    assert os.environ['ANDROID_KEY_PASSWORD']
    (apk,) = Path('bin').glob('*.apk')
    sdk = Path.home() / '.buildozer/android/platform/android-sdk/build-tools'
    signer = sorted(sdk.glob('*/apksigner'))[-1]
    output = apk.with_name(apk.stem + '-signed.apk')
    keypath = None
    try:
        fd, name = tempfile.mkstemp(prefix='nte-sign-', suffix='.keystore')
        keypath = Path(name)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(
                base64.b64decode(os.environ['SIGNING_STORE_B64'], validate=True)
            )
        listing = checked(
            [
                'keytool',
                '-J-Duser.language=en',
                '-J-Duser.country=US',
                '-list',
                '-v',
                '-keystore',
                str(keypath),
                '-storepass:env',
                'ANDROID_KEY_PASSWORD',
            ]
        )
        alias = single_alias(listing)
        checked(
            [
                str(signer),
                'sign',
                '--ks',
                str(keypath),
                '--ks-key-alias',
                alias,
                '--ks-pass',
                'env:ANDROID_KEY_PASSWORD',
                '--key-pass',
                'env:ANDROID_KEY_PASSWORD',
                '--out',
                str(output),
                str(apk),
            ]
        )
        verified = checked(
            [str(signer), 'verify', '--verbose', '--print-certs', str(output)]
        )
        public_lines = [
            line
            for line in verified.splitlines()
            if ' certificate DN: ' in line or ' certificate SHA-256 digest: ' in line
        ]
        with Path('build/certificate_public.txt').open(
            'x', encoding='utf-8', newline='\n'
        ) as stream:
            stream.write('\n'.join(public_lines) + '\n')
        owner, fingerprint = certificate_metadata(verified)
        record = {
            'alias': alias,
            'certificate_owner': owner,
            'certificate_sha256': fingerprint,
            'apk_sha256': hashlib.sha256(output.read_bytes()).hexdigest().upper(),
            'verified': True,
            'version_code': int(os.environ['NTE_VERSION_CODE']),
        }
        with Path('build/signature.json').open(
            'x', encoding='utf-8', newline='\n'
        ) as stream:
            json.dump(record, stream, indent=2)
        print(
            'Fixed-key APK signature verified; certificate metadata recorded (no secret material)'
        )
    finally:
        # Explicit user requirement: only the temporary signing key is removed.
        if keypath is not None:
            keypath.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
