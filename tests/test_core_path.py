import json
from pathlib import Path
import pytest
from core_case_runner import run_case, check_case

FIXTURES = Path(__file__).parent / 'fixtures'
CASES = json.loads((FIXTURES / 'core_cases.json').read_text(encoding='utf-8'))['Cases']


@pytest.mark.parametrize('case', CASES, ids=lambda case: case['CaseID'])
def test_core_path(case):
    check_case(case, run_case(case))


def test_frozen_all_67_and_twelve_old_skip_groups():
    assert len(CASES) == 67 and len({c['CaseID'] for c in CASES}) == 67
    assert len({c['Group'] for c in CASES}) == 12
