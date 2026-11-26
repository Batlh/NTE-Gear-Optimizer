from nte_gear_optimizer.guide.reference import *

def row(**kwargs):
    return {'BeforeValue':'90','AfterValue':'110','TargetMinimum':'100','ReferenceBasis':'PANEL',
        'BeforeBasis':'PANEL','AfterBasis':'PANEL','ContextVerified':True,'CurrentLevel':80,'TargetLevel':80,
        'SubstatPriorityRank':2,'Source':'synthetic','EvidenceID':'test-only',**kwargs}

def test_verified_basis_separate_bonuses_and_raw_delta():
    r=reference(row(ReferenceBasis='VOR_SET',BeforeValue='120',AfterValue='130',BeforeExcludedBonus='20',AfterExcludedBonus='25',
        BonusTransform='ADDITIVE_SAME_UNIT',StatUnit='FLAT',ExcludedBonusUnit='FLAT',ExcludedBonusSource='proof'))
    assert (r['BeforeAligned'],r['AfterAligned'],r['RawDelta'])==('100','105','10')
    r=reference(row(ReferenceBasis=None))
    assert r['RawDelta']=='20' and r['BeforeAligned'] is None
    assert reference(row(ContextVerified=False))['ReferenceUnavailableReason']=='BASIS_UNVERIFIED'

def test_first_changed_rank_not_first_existing_distance_or_maxcap():
    refs=[reference(row(SubstatPriorityRank=1,BeforeValue='150',AfterValue='150')),
          reference(row())]
    assert rank_verdict(refs)['Verdict']=='BETTER'
    assert rank_verdict([reference(row()),reference(row(BeforeValue='110',AfterValue='90'))])['Verdict'] is None
    assert reference(row(TargetMaximum='105'))['AfterAttained'] is True
    assert reference(row(BeforeValue='40',AfterValue='45'))['Trend']=='CLOSER'
    assert decision_rank({'MainstatPriorityRank':4,'SubstatPriorityRank':2})==2

def test_condition_and_priority_conflict_fail_closed_order_independent():
    domains={'Awakening':('A0','A1','A2','A3','A4','A5','A6')}
    c={'Field':'Awakening','Operator':'>=','RequiredValue':'A3'}
    assert condition(c,{'Awakening':'A4'},domains=domains) is True
    assert condition({**c,'Operator':'BAD'},{'Awakening':'A4'},domains=domains) is None
    assert condition({**c,'RequiredValue':'A9'},{'Awakening':'A4'},domains=domains) is None
    v={'Priority':1,'Specificity':1,'Conditions':[c]}
    assert select_target('base',[v],{'Awakening':'A0'},domains=domains)=='base'
    assert select_target('base',[v,{**v,'ID':'2'}],{'Awakening':'A4'},domains=domains) is None

def test_optional_collisions_quarantine_all_no_import_feature():
    a={'UserComparisonTargetID':'same','BuildStateID':'b','StatID':'s','TargetSetID':'t','TargetVariantID':'v'}
    good,bad=quarantine_optional_targets([a,{**a,'StatID':'s2'}])
    assert not good and len(bad)==2

def test_mutants_bonus_default_zero_distance_winner_and_firstrow_killed():
    r=reference(row(ReferenceBasis='VOR_SET'))
    assert r['BeforeAligned'] is None # mutant silently assumes zero exclusion
    result=rank_verdict([reference(row(BeforeValue='40',AfterValue='45'))])
    assert result['Verdict']!='BETTER' # mutant uses distance as recommendation
    assert select_target(None,[{'Priority':1,'Specificity':1},{'Priority':1,'Specificity':1}],{},domains={}) is None
