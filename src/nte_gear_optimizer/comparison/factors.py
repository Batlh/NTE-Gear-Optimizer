"""OPB-05..09: relative static factors, never a combat/DPS simulation."""
from itertools import product
from dataclasses import dataclass
from decimal import Decimal
from ..numbers import number, isolated, ValueUnavailable
from ..panels.resolution import atomic_atk

REACTIONS=('NONE','BLOSSOM','NOVA','SCORCH','HEXED','STAIN')

@dataclass(frozen=True)
class Scenario:
    ratio: Decimal
    before: Decimal
    after: Decimal
    before_scale: Decimal
    after_scale: Decimal
    factor_changed: bool
    states: tuple[str,...]

def read(values, side, field, nonnegative=False):
    return number(values.get(side+field),side+field,nonnegative=nonnegative)

@isolated
def scale(values, side, scaling_stat):
    if scaling_stat not in ('ANG','LP','VER'):
        raise ValueUnavailable('ScalingStat')
    direct=values.get(side+'ScaleDirect')
    if direct is not None:
        return number(direct,side+'ScaleDirect',nonnegative=True)
    if scaling_stat=='ANG':
        return atomic_atk(values.get(side+'CharacterBase'),values.get(side+'ArkBase'),
                          values.get(side+'ATKPP'),values.get(side+'FlatATK'),
                          basis=values.get(side+'WhiteBasis'))
    raise ValueUnavailable(side+'PanelTotal')

@isolated
def cycle(intensity, reaction):
    if reaction=='NONE': return Decimal(1)
    if reaction in ('BLOSSOM','NOVA','SCORCH'): return 1+intensity/600
    if reaction=='HEXED': return 1+Decimal('0.2')*intensity/(intensity+180)
    if reaction=='STAIN': return Decimal('1.2')*(1+Decimal('0.2')*intensity/(intensity+180))
    raise ValueUnavailable('CycleType',True)

@isolated
def factor_values(values, side, profile, crit, brk, reaction):
    kind=profile.get('ProfileType')
    if kind=='BUFF': return (Decimal(1),)
    if kind in ('HEAL','SHIELD'):
        factor=1+read(values,side,'HealingPP' if kind=='HEAL' else 'ShieldPP')/100
        if factor<0:raise ValueUnavailable(side+'Factor',True)
        return (factor,)
    if kind!='DAMAGE': raise ValueUnavailable('ProfileType')
    bonus=1+(sum(read(values,side,k) for k in ('UniversalPP','ElementPP','SkillPP','OtherPP'))-
             read(values,side,'ReductionPP'))/100
    crit_factor=Decimal(1)
    if crit=='TRUE':
        crit_factor+=read(values,side,'CritRatePP',True)*read(values,side,'CritDamagePP',True)/10000
    break_factor=Decimal(1)
    if brk=='TRUE':
        break_factor+=read(values,side,'Break',True)/300+read(values,side,'ExtraBreakBuff')
    cycle_factor=cycle(read(values,side,'CycleIntensity',True),reaction) if reaction!='NONE' else Decimal(1)
    factors=(bonus,crit_factor,break_factor,cycle_factor)
    if any(f<0 for f in factors):raise ValueUnavailable(side+'Factor',True)
    return factors

def domain(profile, field, closed):
    value=profile.get(field)
    if value=='UNKNOWN':return closed
    if value in closed:return (value,)
    raise ValueUnavailable(field,value is not None)

@isolated
def scenarios(values, profile):
    before=scale(values,'Before',profile.get('ScalingStat'))
    after=scale(values,'After',profile.get('ScalingStat'))
    if before<=0:raise ValueUnavailable('BeforeScaleDirect',True)
    domains=(domain(profile,'CritEligible',('FALSE','TRUE')),
             domain(profile,'BreakEligible',('FALSE','TRUE')),
             domain(profile,'CycleType',REACTIONS)) if profile.get('ProfileType')=='DAMAGE' else (('FALSE',),('FALSE',),('NONE',))
    result=[]
    for states in product(*domains):
        bf=factor_values(values,'Before',profile,*states)
        af=factor_values(values,'After',profile,*states)
        bp,ap=before,after
        ratio=after/before
        for b,a in zip(bf,af):
            if b<=0:raise ValueUnavailable('BeforeFactor')
            bp*=b;ap*=a
            # Cancel unchanged, defined factors exactly, avoiding rounding noise.
            if a!=b:ratio*=a/b
        result.append(Scenario(ratio,bp,ap,before,after,bf!=af,states))
    return tuple(result)
