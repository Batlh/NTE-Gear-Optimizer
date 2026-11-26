"""Execute valid, deliberately mutated source against semantic oracles.

No production files are changed. Syntax/import errors do not count as kills.
The same probes run under CPython and Pyodide.
"""
import importlib,sys,types
from pathlib import Path
from decimal import Decimal
from nte_gear_optimizer.numbers import ValueUnavailable

P={'ProfileType':'DAMAGE','ScalingStat':'ANG','CritEligible':'FALSE','BreakEligible':'FALSE','CycleType':'NONE'}
def values():
    return {**{s+k:'0' for s in ('Before','After') for k in ('UniversalPP','ElementPP','SkillPP','OtherPP','ReductionPP')},
            'BeforeScaleDirect':'100','AfterScaleDirect':'110'}

def probe_profile(m):
    r=m.effective_profile({'CritEligible':'FALSE'},{'CritEligible':'TRUE'},branch_id='B',override_branch_id='A')
    assert r.values['CritEligible']=='FALSE'
def probe_layout(m):
    mask={(r,c) for r in range(1,6) for c in range(1,6)}-{(1,3),(4,1),(4,5),(5,1),(5,5)}
    assert m.layout(['x'],[{'cells':[(3,1)]}],mask) is None
def probe_direct(m):
    o=dict(StatID='STAT_ATK',DirectInputValue='1234',BuildStateFingerprint='F',RulesetID='R',InActiveTeam=False,
           ObservationKind='PANEL_TOTAL',CaptureContext=None,Provenance='synthetic',ExternalDeclarations={k:'NONE_DECLARED' for k in m.EXTERNAL_CLASSES})
    assert m.resolve_channel('STAT_ATK','DIRECT',observation=o,expected_fingerprint='F',ruleset_id='R')['ActualValue'] is None
def probe_modes(m):
    assert m.resolve_channel('STAT_CRIT_RATE','DIRECT').get('ErrorCode')=='ERR_CHANNEL_MODE_NOT_SUPPORTED_V028'
def probe_break(m):
    v={**values(),'BeforeBreak':'0','AfterBreak':'300','BeforeExtraBreakBuff':'0','AfterExtraBreakBuff':'0'}
    assert m.scenarios(v,{**P,'BreakEligible':'TRUE'})[0].ratio==Decimal('2.2')
def probe_float(m):assert m.number('0.100000000000000000000000000001')==Decimal('0.100000000000000000000000000001')
def probe_unknown(m):assert m.domain({'CritEligible':'UNKNOWN'},'CritEligible',('FALSE','TRUE'))==('FALSE','TRUE')
def probe_epsilon(m):
    v={**values(),'AfterScaleDirect':'150','BeforeCritRatePP':'0','AfterCritRatePP':'0.00000000001','BeforeCritDamagePP':'100','AfterCritDamagePP':'100'}
    assert m.evaluate_profile(v,{**P,'CritEligible':'UNKNOWN'})['RawRatio'] is None
def probe_branch(m):
    r=m.evaluate_branches([m.Branch('a',P),m.Branch('b',P,{'AfterScaleDirect':'90'})],values())
    assert r['BranchStatus']=='BRANCHES_DISAGREE'
def guide_row(**kwargs):
    return {'BeforeValue':'90','AfterValue':'110','TargetMinimum':'100','ReferenceBasis':'PANEL','BeforeBasis':'PANEL','AfterBasis':'PANEL',
            'ContextVerified':True,'CurrentLevel':80,'TargetLevel':80,'SubstatPriorityRank':2,'Source':'SYNTHETIC','EvidenceID':'test-only',**kwargs}
def probe_rank(m):
    refs=[m.reference(guide_row(BeforeValue='150',AfterValue='150',SubstatPriorityRank=1)),m.reference(guide_row())]
    assert m.rank_verdict(refs)['Verdict']=='BETTER'
def probe_gate(m):
    r=m.compare(values(),P,targets=[guide_row(ReferenceBasis=None)])
    assert r['OutputStatus']=='READY' and r['Verdict']=='BETTER'
def probe_projection(m):
    r=m.project({'WhiteBasis':'IN_GAME_WHITE_WITH_PROGRESS','WhiteCurrent':'100','White80':'200','ActualTotal':'1000','EquipmentPercent':None})
    assert r['ProjectedLv80Exact'] is None
def probe_score(m):
    weights={**{str(i):'10' for i in range(4)},**{str(i):'1' for i in range(4,8)}}
    rolls=[{'StatID':str(i),'Value':'10','Baseline':'10','Minimum':'0','Maximum':'10'} for i in range(4,8)]
    policy={'Maximum score':'1','Build relevance share':'0.6','Roll quality share':'0.4','Keep threshold':'0.85','Review threshold':'0.65'}
    r=m.score_item(rolls,weights,policy,required_slots=4)
    assert r['Overall']=='0.46' and r['Recommendation']=='Recycle'

# (module, ID, unique replacement pairs, semantic oracle)
MUTATIONS=[
 ('models.profile_state','M02_BRANCH_LEAK', [('bound = override_branch_id == branch_id','bound = True')],probe_profile),
 ('validation.scoped','M03_AXES_TRANSPOSED', [('tuple(cell) for p in placements','tuple(reversed(cell)) for p in placements')],probe_layout),
 ('panels.resolution','M04_CONTEXT_BYPASS', [('if not valid:','if False:')],probe_direct),
 ('panels.resolution','M04_MODE_BOUNDARY_REMOVED', [('if stat_id in UNSUPPORTED_MODES:','if False:')],probe_modes),
 ('numbers','M05_FLOAT_DECIMAL', [('n=Decimal(value)','n=Decimal(float(value))')],probe_float),
 ('comparison.factors','M05_BREAK_DIVISOR', [("side,'Break',True)/300","side,'Break',True)/600")],probe_break),
 ('comparison.factors','M06_UNKNOWN_FALSE', [("if value=='UNKNOWN':return closed","if value=='UNKNOWN':return (closed[0],)")],probe_unknown),
 ('comparison.robust_branches','M06_EPSILON', [('if lo==hi:',"if abs(lo-hi)<=Decimal('0.000000000001'):")],probe_epsilon),
 ('comparison.robust_branches','M06_FIRST_BRANCH', [("verdicts={r['Verdict'] for r in evaluated}","verdicts={evaluated[0]['Verdict']}")],probe_branch),
 ('guide.reference','M07_FIRST_EXISTING_RANK', [("rank=min(r['DecisionRank'] for r in changed)","rank=min(r['DecisionRank'] for r in references if r['DecisionRank'] is not None)")],probe_rank),
 ('comparison.recommendation','M08_GLOBAL_GUIDE_GATE', [('    if layout_issue is not None:',"    if any(r['ReferenceUnavailableReason'] for r in refs):out.update(OutputStatus=MISSING,Verdict=None)\n    if layout_issue is not None:")],probe_gate),
 ('projection.lv80','M09_NULL_PERCENT_ZERO', [("if values.get('EquipmentPercent') is not None:",'if True:'),("number(values['EquipmentPercent'],'EquipmentPercent'","number(values.get('EquipmentPercent') or '0','EquipmentPercent'")],probe_projection),
 ('legacy.item_score','M10_SELECTED_STATS_DENOMINATOR', [('best=sum(sorted(all_weights.values(),reverse=True)[:required_slots])','best=selected')],probe_score),
]

def run_mutations():
    report=[]
    for suffix,identifier,changes,probe in MUTATIONS:
        original=importlib.import_module('nte_gear_optimizer.'+suffix)
        probe(original)
        source=Path(original.__file__).read_text(encoding='utf-8')
        for old,new in changes:
            assert source.count(old)==1,(identifier,'ambiguous mutation')
            source=source.replace(old,new)
        name='_nte_mutant_'+identifier
        module=types.ModuleType(name);module.__package__=original.__package__;module.Decimal=Decimal
        sys.modules[name]=module
        try:
            exec(compile(source,original.__file__,'exec'),module.__dict__)
            try:probe(module)
            except AssertionError:report.append({'ID':identifier,'Result':'KILLED'})
            else:raise AssertionError(identifier+' survived')
        finally:
            del sys.modules[name]
    return report
