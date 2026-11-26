from decimal import Decimal, localcontext
import pytest
from nte_gear_optimizer.panels.resolution import *
from nte_gear_optimizer.numbers import ValueUnavailable

def observation():
    return dict(StatID='STAT_ATK',DirectInputValue='1234',BuildStateFingerprint='F',RulesetID='R',
        CaptureContext='PANEL',Provenance='synthetic',InActiveTeam=False,ObservationKind='PANEL_TOTAL',
        ExternalDeclarations={k:'NONE_DECLARED' for k in EXTERNAL_CLASSES})

def resolve(o, **kwargs):
    return resolve_channel('STAT_ATK','DIRECT',observation=o,expected_fingerprint='F',ruleset_id='R',**kwargs)

def test_atomic_no_double_count_or_missing_zero():
    assert atomic_atk('100','100','20','10',basis='IN_GAME_WHITE_WITH_PROGRESS')==250
    with pytest.raises(ValueUnavailable,match='FlatATK'):
        atomic_atk('100','100','20',None,basis='IN_GAME_WHITE_WITH_PROGRESS')
    with localcontext() as ctx:
        ctx.prec=2
        assert atomic_atk('100','100','20','10',basis='IN_GAME_WHITE_WITH_PROGRESS')==250

def test_all_mode_channels_and_raw_boundary():
    assert len(UNSUPPORTED_MODES)==23
    for stat in UNSUPPORTED_MODES:
        assert resolve_channel(stat,'DIRECT')['ErrorCode']=='ERR_CHANNEL_MODE_NOT_SUPPORTED_V028'
    for stat in ('STAT_ATK','STAT_HP','STAT_DEF'):
        assert resolve_channel(stat,'ATOMIC',atomic_basis='RAW_LEVEL_STAT')['ErrorCode']=='ERR_CHANNEL_CHARACTER_PANEL_BASE_MISSING'

def test_direct_context_missing_candidate_and_freshness():
    o=observation()
    assert resolve(o)['ActualValue']=='1234'
    assert resolve_channel('STAT_ATK','DIRECT')['ActualValue'] is None
    for key in EXTERNAL_CLASSES:
        bad=observation(); del bad['ExternalDeclarations'][key]
        assert resolve(bad)['ActualValue'] is None
    for key,value in [('BuildStateFingerprint','wrong'),('RulesetID','wrong'),('ObservationKind','CONSOLE_TAB')]:
        assert resolve({**o,key:value})['ActualValue'] is None
    assert resolve({**o,'InActiveTeam':True})['ActualValue'] is None
    o.update(InActiveTeam=True,ObservedLocalDate='2026-11-27')
    assert resolve(o,comparison_day='2026-11-26')['Notice']=='Panelwert evtl. veraltet (Tagesbonus)'
    assert resolve(o)['Freshness']=='UNKNOWN'

def test_mutants_cache_context_bypass_and_float_killed():
    o=observation();o['CaptureContext']=None
    # A cache-only implementation would incorrectly return 1234 here.
    assert resolve(o)['ActualValue'] != '1234'
    with pytest.raises(ValueUnavailable):
        atomic_atk(0.1,'100','20','10',basis='IN_GAME_WHITE_WITH_PROGRESS')
    o=observation();o.update(FixtureType='SYNTHETIC_TEST_FIXTURE',ExecutionEnvironment='TEST_HARNESS',ProductionEligibility='FORBIDDEN')
    assert resolve(o)['ActualValue'] is None
    assert resolve(o,allow_synthetic=True)['ActualValue']=='1234'
