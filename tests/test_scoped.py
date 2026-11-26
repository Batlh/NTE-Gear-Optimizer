from nte_gear_optimizer.validation.scoped import *

MASK = {(r,c) for r in range(1,6) for c in range(1,6)} - {(1,3),(4,1),(4,5),(5,1),(5,5)}

def test_layout_phase_order_and_axis():
    assert layout(['x'],[{'cells':[(3,1)]}],MASK) is None
    assert layout(['x'],[{'cells':[(1,3)]}],MASK).code=='ERR_LAYOUT_BLOCKED_CELL'
    assert layout(['x'],[{'cells':[(6,1)]}],MASK).code=='ERR_LAYOUT_OUT_OF_BOUNDS'
    assert layout(list(range(11)),[],None).code=='ERR_LAYOUT_MODULE_COUNT_INVALID'
    assert layout([],[],None).code=='ERR_LAYOUT_MASK_REQUIRED'
    assert layout(['x','y'],[{'cells':[(1,1)]},{'cells':[(1,1)]}],MASK).code=='ERR_LAYOUT_OVERLAP'
    assert layout(['x'],[{'cells':[(1,1)],'rotation':90}],MASK).code=='ERR_LAYOUT_TRANSFORM_NOT_ALLOWED'

def test_progress_and_resonance_are_local():
    caps={0:20,1:30,2:40,3:50,4:60,5:70,6:80}
    assert ark_progress(3,40,caps)==(None,'AVAILABLE')
    assert ark_progress(3,39,caps).code=='ERR_STATE_ARK_LEVEL_BELOW_ASCENSION_FLOOR'
    assert ark_progress(3,60,caps).outcome=='ARK_INSTANCE_NO_DEPENDENT_OUTPUT'
    assert ark_progress(None,50,caps).field=='ArkAscensionStage'
    assert not character_level_valid(0) and character_level_valid(80)
    assert resonance(2)==() and resonance(3)==('R3',) and resonance(6)==('R3','R6')
    assert resonance(9) is None

def test_mutants_axis_transpose_and_global_ark_gate_killed():
    placement=[{'cells':[(3,1)]}]
    assert layout(['x'],placement,MASK) is None
    transposed=[{'cells':[(c,r) for r,c in placement[0]['cells']]}]
    assert layout(['x'],transposed,MASK) is not None
    issue=ark_progress(None,20,{0:20})
    assert issue.outcome!='BUILD_INVALID_NO_CHANNEL_OUTPUT'


def test_validator_coverage_and_missing_unreferenced_qa():
    rows=[{'ID':'good','Level':80},{'ID':'bad','Level':0}]
    validators={'Level':lambda row:character_level_valid(row.get('Level'))}
    assert validate_selected(rows,'ID','good',validators,['Level'])['Status']=='PASS'
    assert validate_selected(rows,'ID','good',{},['Level'])['Status']=='UNKNOWN'
    assert validate_selected(rows,'ID','bad',validators,['Level'])['Status']=='FAIL'

def test_character_nullable_axes_and_slots():
    assert character_state({'Level':80,'AwakeningStage':0,'AwakeningEffectSelection':[]},allowed_slots=[])['AwakeningEffectSelection'] is True
    assert character_state({'Level':80,'AwakeningStage':3},allowed_slots=['a','b','c'])['AwakeningEffectSelection'] is None
    assert character_state({'Level':80,'AwakeningStage':3,'AwakeningEffectSelection':['a','a','b']},allowed_slots=['a','b','c'])['AwakeningEffectSelection'] is False

def test_item_main_pairs_unit_source_point_and_locked_substat():
    rows=[{'Role':'MAIN','Slot':1,'StatID':'STAT_ATK','Unit':'FLAT','Value':'100'},
          {'Role':'MAIN','Slot':2,'StatID':'STAT_HP','Unit':'FLAT','Value':'200'},
          {'Role':'SUB','Slot':1,'StatID':'STAT_CRIT_RATE','Unit':'PP','Value':'5'}]
    kwargs=dict(kind='MODULE',level=0,stat_units={'STAT_ATK':'FLAT','STAT_HP':'FLAT','STAT_CRIT_RATE':'PP'},permitted_main_ids=set(),
        limits={('MAIN',1,'STAT_ATK'):('0','100'),('MAIN',2,'STAT_HP'):('0','200')})
    r=item_stats(rows,**kwargs)
    assert r['Status']=='PASS' and r['ActiveSubstats']==[]
    assert item_stats(rows,**{**kwargs,'limits':{}})['Status']=='UNKNOWN'
    assert item_stats(rows[:1],**kwargs)['Status']=='FAIL'


def test_missing_unlocked_slot_cannot_pass_item_validation():
    rows=[{'Role':'MAIN','Slot':1,'StatID':'STAT_ATK','Unit':'FLAT','Value':'100'}]
    params=dict(kind='CARTRIDGE',level=5,stat_units={'STAT_ATK':'FLAT'},permitted_main_ids={'STAT_ATK'},limits={('MAIN',1,'STAT_ATK'):('0','100')})
    assert item_stats(rows,**params)=={'Status':'UNKNOWN','Field':'SubStats'}
