from nte_gear_optimizer.comparison.recommendation import *
from nte_gear_optimizer.validation.scoped import ark_progress,Issue
from test_factors import P,values
from test_reference import row

def test_missing_unrelated_dependency_preserves_product_and_deltas():
    r=compare(values(),P,ark_issue=ark_progress(None,20,{0:20}),targets=[row(ReferenceBasis=None)])
    assert r['Verdict']=='BETTER' and r['RawRatio']=='1.1'
    assert r['Deltas']['ScaleDirect']=='10' and r['ArkDependentOutputs']=='UNKNOWN'
    assert r['ReferenceUnavailableReason']=='BASIS_UNVERIFIED' and not r['DroveRecommendation']

def test_product_wins_over_guide_but_invariant_scale_uses_rank():
    assert compare(values(),P,targets=[row(BeforeValue='110',AfterValue='90')])['Verdict']=='BETTER'
    assert compare({**values(),'ScalingStat':'SONSTIGE'},P,targets=[row()])['Verdict']=='BETTER'
    assert compare({**values(),'ScalingStat':'SONSTIGE'},P,targets=[])['OutputStatus']=='NICHT_ENTSCHEIDBAR'

def test_conditional_reversal_and_local_layout_scope():
    r=compare(values(),P,conditional_factors=[{'BeforeFactor':'1','AfterFactor':'1'}, {'BeforeFactor':'1.2','AfterFactor':'1'}])
    assert r['OutputStatus']=='INDETERMINATE_CONDITIONAL_COMPONENT' and r['BaseProxyRatio']=='1.1'
    r=compare(values(),P,layout_issue=Issue('ERR_LAYOUT_BLOCKED_CELL','BUILD_INVALID_NO_CHANNEL_OUTPUT','Row/Column','blocked'))
    assert r['Verdict'] is None and r['ItemDeltas']=='PRESERVED' and r['Deltas']['ScaleDirect']=='10'

def test_rulesets_and_mutant_global_gate():
    assert compare(values(),P,ruleset='SUPERSEDED')['Verdict']=='BETTER'
    assert compare(values(),P,ruleset='UNKNOWN')['Verdict'] is None
    correct=compare(values(),P,targets=[row(ReferenceBasis=None)])
    # Incorrect global guide gate would erase this independent, known product.
    assert correct['OutputStatus']=='READY' and correct['ReferenceUnavailableReason']


def test_valid_ark_progress_is_not_marked_unknown():
    r=compare(values(),P,ark_issue=ark_progress(3,40,{2:40,3:50}))
    assert 'ArkDependentOutputs' not in r and r['Verdict']=='BETTER'
    issue=ark_progress(3,40,{})
    assert issue.code is None and issue.field=='UnlocksMaxLevel'
    r=compare(values(),P,ark_issue=issue)
    assert r['ArkDependentOutputs']=='UNKNOWN' and r['Verdict']=='BETTER'
