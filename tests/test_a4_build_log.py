import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    'a4_build', Path(__file__).resolve().parents[1] / 'tools/a4_run_android_build.py'
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_credential_related_lines_are_not_saved_in_tail():
    for line in [
        'TOKEN=fixture_not_a_real_credential',
        'password: fixture_not_a_real_credential',
        'Authorization: fixture',
    ]:
        assert 'fixture' not in module.safe_line(line)
    assert (
        module.safe_line('compiler: missing libfixture\n')
        == 'compiler: missing libfixture\n'
    )
    assert len(module.safe_line('a' * 5000)) < 4050


def test_remote_terminal_controls_are_removed_before_artifact_output():
    assert (
        module.safe_line('\x1b[31mcompiler: fixture\x1b[0m\n') == 'compiler: fixture\n'
    )
    assert '\x1b' not in module.safe_line('\x1b]0;fixture\x07')
