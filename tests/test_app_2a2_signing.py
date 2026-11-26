import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'sign_android', ROOT / 'tools/sign_android.py'
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_exactly_one_private_key_required():
    assert (
        module.single_alias('Alias name: project-key\nEntry type: PrivateKeyEntry\n')
        == 'project-key'
    )
    for listing in [
        '',
        'Alias name: a\nEntry type: trustedCertEntry',
        'Alias name: a\nAlias name: b\nEntry type: PrivateKeyEntry\nEntry type: PrivateKeyEntry',
    ]:
        with pytest.raises(ValueError):
            module.single_alias(listing)


def test_signing_rejects_non_ci_without_loading_secrets(monkeypatch):
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    with pytest.raises(AssertionError):
        module.main()


def test_signer_does_not_echo_password_failures(monkeypatch):
    class Failed:
        returncode = 1
        stdout = 'sensitive output must not be shown'
        stderr = 'sensitive output must not be shown'

    monkeypatch.setattr(module.subprocess, 'run', lambda *a, **kw: Failed())
    with pytest.raises(RuntimeError) as error:
        module.checked(['nonexecuted-command'])
    assert 'sensitive output' not in str(error.value)


def test_workflow_signing_scope_and_no_password_commandline():
    workflow = (ROOT / '.github/workflows/app.yml').read_text(encoding='utf-8')
    assert 'pull_request_target' not in workflow
    assert "github.event_name == 'push'" in workflow
    script = (ROOT / 'tools/sign_android.py').read_text(encoding='utf-8')
    assert "'env:ANDROID_KEY_PASSWORD'" in script and "'-storepass:env'" in script
    assert 'keypath.unlink' in script


@pytest.mark.parametrize(
    'prefix',
    [
        'Signer #1',
        'V2 Signer:',
        'V3.1 Signer: (minSdkVersion=33, maxSdkVersion=2147483647)',
    ],
)
def test_public_certificate_formats(prefix):
    output = (
        prefix
        + ' certificate DN: CN=NTE Gear Optimizer Release\n'
        + prefix
        + ' certificate SHA-256 digest: '
        + 'ab' * 32
        + '\n'
    )
    assert module.certificate_metadata(output) == (
        'CN=NTE Gear Optimizer Release',
        'AB' * 32,
    )


def test_debug_and_inconsistent_certificates_are_rejected():
    output = (
        'V2 Signer: certificate DN: CN=Android Debug\nV2 Signer: certificate SHA-256 digest: '
        + 'ab' * 32
    )
    with pytest.raises(ValueError):
        module.certificate_metadata(output)
    with pytest.raises(ValueError):
        module.certificate_metadata('Verifies without public metadata')
