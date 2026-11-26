from decimal import Decimal,localcontext
import pytest
from nte_gear_optimizer.comparison.factors import *

P={'ProfileType':'DAMAGE','ScalingStat':'ANG','CritEligible':'FALSE','BreakEligible':'FALSE','CycleType':'NONE'}
def values():
    return {**{s+k:'0' for s in ('Before','After') for k in ('UniversalPP','ElementPP','SkillPP','OtherPP','ReductionPP')},
        'BeforeScaleDirect':'100','AfterScaleDirect':'110'}

def test_crit_break_cycle_and_relevant_fields():
    v=values();v.update(BeforeCritRatePP='50',AfterCritRatePP='60',BeforeCritDamagePP='100',AfterCritDamagePP='100')
    assert scenarios(v,{**P,'CritEligible':'TRUE'})[0].ratio > Decimal('1.1733333333')
    v.update(BeforeBreak='0',AfterBreak='300',BeforeExtraBreakBuff='0',AfterExtraBreakBuff='0')
    assert scenarios(v,{**P,'BreakEligible':'TRUE'})[0].ratio==Decimal('2.2')
    assert cycle(Decimal(600),'BLOSSOM')==2
    assert cycle(Decimal(180),'HEXED')==Decimal('1.1')
    assert cycle(Decimal(180),'STAIN')==Decimal('1.32')
    for kind,field in [('HEAL','HealingPP'),('SHIELD','ShieldPP')]:
        # Missing crit/break/cycle and all damage bonuses must not gate healing/shield.
        clean={'BeforeScaleDirect':'100','AfterScaleDirect':'110','Before'+field:'0','After'+field:'10'}
        assert scenarios(clean,{'ProfileType':kind,'ScalingStat':'LP'})[0].ratio==Decimal('1.21')

def test_unknown_enumerates_full_domain_and_zero_negative_missing():
    v=values()
    v.update({s+k:'0' for s in ('Before','After') for k in ('CritRatePP','CritDamagePP','Break','ExtraBreakBuff','CycleIntensity')})
    assert len(scenarios(v,{**P,'CritEligible':'UNKNOWN','BreakEligible':'UNKNOWN','CycleType':'UNKNOWN'}))==24
    assert scenarios({**v,'AfterScaleDirect':'0'},P)[0].ratio==0
    for key,val in [('AfterScaleDirect','-999'),('BeforeScaleDirect','0'),('AfterScaleDirect',0.1),('BeforeUniversalPP',None)]:
        with pytest.raises(ValueUnavailable):scenarios({**v,key:val},P)

def test_context_isolation_and_mutants():
    v=values()
    with localcontext() as ctx:
        ctx.prec=2
        assert scenarios(v,P)[0].ratio==Decimal('1.1')
    # Mutated divisors and float construction are observably wrong.
    assert cycle(Decimal(600),'NOVA') != 1+Decimal(600)/300
    assert Decimal(0.1) != number('0.1')
    with pytest.raises(ValueUnavailable):
        scenarios({**v,'BeforeFlatATK':None,'BeforeScaleDirect':None},P)
