from nte_gear_optimizer.validation.scoped import validate_selected
from nte_gear_optimizer.comparison.recommendation import compare
from nte_gear_optimizer.comparison.robust_branches import Branch,evaluate_branches
from nte_gear_optimizer.guide.reference import reference,condition
from test_factors import P,values
from test_reference import row

def test_validator_string_fail_is_never_pass():
    for token in ('PASS','FAIL','',0,1):
        r=validate_selected([{'ID':'x'}],'ID','x',{'check':lambda r:token},['check'])
        assert r['Status']=='UNKNOWN'

def test_guide_needs_actual_provenance_and_id_gte_is_not_ordered():
    assert reference(row(Source=None))['ReferenceUnavailableReason']=='BASIS_UNVERIFIED'
    assert condition({'Field':'BuildID','RequiredValue':'b','Operator':'>='},{'BuildID':'c'},domains={'BuildID':('b','c')}) is None

def test_robust_conditional_range_and_unknown_factor_cross_product():
    r=compare(values(),P,conditional_factors=[{'BeforeFactor':'1','AfterFactor':'1'},{'BeforeFactor':'1','AfterFactor':'2'}])
    assert r['Verdict']=='BETTER' and r['RawRatio'] is None and r['RatioMin']=='1.1' and r['RatioMax']=='2.2'
    v={**values(),'CritEligible':'UNKNOWN','BeforeCritRatePP':'0','AfterCritRatePP':'100','BeforeCritDamagePP':'100','AfterCritDamagePP':'100'}
    r=compare(v,P,conditional_factors=[{'BeforeFactor':'3','AfterFactor':'1'},{'BeforeFactor':'1','AfterFactor':'1'}])
    assert r['OutputStatus']=='INDETERMINATE_CONDITIONAL_COMPONENT'

def test_foreign_branch_profile_local_and_invariant_guide_per_branch():
    r=compare(values(),{**P,'BuildProfileID':'P'},branches=[Branch('b',{**P,'BuildProfileID':'OTHER'})])
    assert r['ProductDerivationStatus']=='FAIL' and r['ItemDeltas']=='PRESERVED'
    b=Branch('b',{**P,'ScalingStat':'SONSTIGE'},targets=(row(),))
    assert evaluate_branches([b],values())['Verdict']=='BETTER'
    assert evaluate_branches([b],values(),expected_ids=['b','b'])['OutputStatus']=='INDETERMINATE_MISSING_DEPENDENCY'
