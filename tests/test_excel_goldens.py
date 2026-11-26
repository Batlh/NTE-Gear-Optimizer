"""Auditor-generated native values; contract precedence is explicit, not patched."""
import json
from pathlib import Path
from decimal import Decimal
import pytest
from core_case_runner import run_case,check_case
from nte_gear_optimizer.rules.opb10 import evaluate

ROOT=Path(__file__).parent/'fixtures'
CASES={c['CaseID']:c for c in json.loads((ROOT/'core_cases.json').read_text(encoding='utf-8'))['Cases']}
GOLDENS=json.loads((ROOT/'excel_goldens.json').read_text(encoding='utf-8'))

@pytest.mark.parametrize('golden',GOLDENS['Cases'],ids=lambda row:row['CaseID'])
def test_bound_excel_golden(golden):
    case=CASES[golden['CaseID']]
    assert json.loads(golden['ContractExpected'])==case['Expected']
    r=run_case(case);check_case(case,r)
    if golden['Status']=='NICHT_DARSTELLBAR':
        assert golden['Excel']=={} or all(v is None for v in golden['Excel'].values())
        assert golden['Gap']
        return
    assert len(golden['RecalculatedCopySHA256'])==64
    excel=golden['Excel']
    if case['CaseID']=='KP03_UNVERIFIED_GUIDE':
        assert excel['v028 Comparison!BH6']=='INDETERMINATE_MISSING_DEPENDENCY'
        assert r['OutputStatus']=='READY' and r['Verdict']=='BETTER'
        return # PLATTFORM-15, §13: guide absence cannot gate known product.
    assert r['OutputStatus']==excel['v028 Comparison!BH6']
    assert r['Verdict']==excel['v028 Comparison!BG6']
    if case['CaseID']=='KP04_AFTER_NEGATIVE':
        assert excel['v028 Comparison!BE6']=='-9.99' and r['RawRatio'] is None
    elif excel.get('v028 Comparison!BF6') is not None:
        # Native binary display may differ; OPB-10 decimal rounding takes precedence.
        assert r['VerdictRatio']==evaluate(excel['v028 Comparison!BF6']).rounded
    if case['CaseID']=='KP08_AFFINE_NEAR':
        assert r['BranchStatus']==excel['v028 Comparison!CE6']
        assert r['BranchEvaluations'][0]['AffineStatus']==excel['v028 Comparison!P316']

def test_golden_binding_and_counts():
    assert GOLDENS['SourceSHA256']=='1D0C586B9FD9289584150EE21687340382256FE16B0DC4D5008453204C49E168'
    assert sum(r['Status']=='NATIVE_ERZEUGT' for r in GOLDENS['Cases'])==10
    assert sum(r['Status']=='NICHT_DARSTELLBAR' for r in GOLDENS['Cases'])==4
