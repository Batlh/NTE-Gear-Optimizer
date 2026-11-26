from nte_gear_optimizer.comparison.robust_branches import *
from test_factors import values,P

def crit_values(after):
    return {**values(),'AfterScaleDirect':after,'BeforeCritRatePP':'0','AfterCritRatePP':'100',
            'BeforeCritDamagePP':'100','AfterCritDamagePP':'100'}

def test_unknown_robust_disagreement_and_missing():
    p={**P,'CritEligible':'UNKNOWN'}
    r=evaluate_profile(crit_values('75'),p)
    assert r['OutputStatus']==MISSING and r['RatioMin']=='0.75' and r['RatioMax']=='1.5'
    r=evaluate_profile(crit_values('150'),p)
    assert r['Verdict']=='BETTER' and r['RawRatio'] is None
    r=evaluate_profile({**crit_values('150'),'AfterCritDamagePP':None},p)
    assert r['OutputStatus']==MISSING and r['RatioMin']=='1.5' and r['RawRatio'] is None

def test_exact_equality_no_epsilon():
    v=crit_values('150');v['AfterCritRatePP']='0.00000000001'
    r=evaluate_profile(v,{**P,'CritEligible':'UNKNOWN'})
    assert r['Verdict']=='BETTER' and r['RawRatio'] is None
    assert r['RatioMin']!=r['RatioMax']

def test_branch_disagreement_missing_unknown_and_order():
    a=Branch('a',P);b=Branch('b',P,{'AfterScaleDirect':'90'})
    r=evaluate_branches([a,b],values())
    assert r['BranchStatus']=='BRANCHES_DISAGREE' and r['RawRatio'] is None
    assert evaluate_branches([b,a],values())==r
    assert evaluate_branches([a],values(),expected_ids=['a','b'])['OutputStatus']==MISSING
    u=Branch('u',{**P,'CritEligible':'UNKNOWN'},crit_values('75'))
    assert evaluate_branches([a,u],values())['OutputStatus']==MISSING
    assert evaluate_branches([a,a],values())['OutputStatus']==MISSING

def shield(v, **kwargs):
    return evaluate_profile(v,{'ProfileType':'SHIELD','ScalingStat':'VER'},offset_status='POSITIVE',offset_minimum='1000',coefficient='0.8',**kwargs)

def test_affine_per_branch_and_equal_is_not_near():
    v={'BeforeScaleDirect':'3000','AfterScaleDirect':'3020','BeforeShieldPP':'0','AfterShieldPP':'0'}
    assert shield(v)['AffineStatus']=='FIXED_OFFSET_NEAR_THRESHOLD'
    assert shield({**v,'AfterScaleDirect':'3001'})['Verdict']=='EQUAL'
    assert shield({**v,'AfterScaleDirect':'3100'})['AffineStatus']=='AFFINE_THRESHOLD_CROSSED'
    assert shield({**v,'AfterShieldPP':'10'})['AffineStatus']=='AFFINE_OFFSET_NOT_MODELLED'
    assert shield({**v,'AfterScaleDirect':'3000','AfterShieldPP':'10'})['AffineStatus']=='AFFINE_PROXY_ALLOWED'
    assert evaluate_profile(values(),P,offset_status='UNKNOWN')['Notice']=='FIXED_OFFSET_STATUS_UNKNOWN'

def test_mutants_first_row_average_epsilon_and_unknown_false_killed():
    v=crit_values('75');p={**P,'CritEligible':'UNKNOWN'}
    correct=evaluate_profile(v,p)
    assert evaluate_profile(v,{**p,'CritEligible':'FALSE'})['OutputStatus']!=correct['OutputStatus']
    a=Branch('a',P);b=Branch('b',P,{'AfterScaleDirect':'90'})
    assert evaluate_branches([a,b],values())['Verdict']!=evaluate_profile(values(),P)['Verdict']
    # Mutant averaging 1.1 and .9 would emit EQUAL, while correct result has no verdict.
    assert evaluate_branches([a,b],values())['Verdict']!='EQUAL'
