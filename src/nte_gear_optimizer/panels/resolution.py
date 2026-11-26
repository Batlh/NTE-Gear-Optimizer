"""OPB-02 and DIRECT observation contract; no cache is an observation."""
from datetime import date
from ..numbers import number, text, isolated, ValueUnavailable

UNSUPPORTED_MODES = frozenset('STAT_ANIMA_DMG STAT_ATK_FLAT STAT_ATK_PCT STAT_BREAK_INTENSITY STAT_CHAOS_DMG STAT_CHARGE_EFFICIENCY STAT_COSMOS_DMG STAT_CRIT_DMG STAT_CRIT_RATE STAT_CYCLE_INTENSITY STAT_DEF_FLAT STAT_DEF_PCT STAT_ENEMY_CHAOS_RES_IGNORE STAT_ENEMY_DEF_IGNORE STAT_HEALING STAT_HP_FLAT STAT_HP_PCT STAT_INCANTATION_DMG STAT_LAKSHANA_DMG STAT_MENTAL_DMG STAT_PSYCHE_DMG STAT_SHIELD_STRENGTH STAT_UNIVERSAL_DMG'.split())
EXTERNAL_CLASSES = ('Furniture','Account','Collection','Event','UnknownExternal')

@isolated
def atomic_atk(character_base, ark_base, equipment_pp, flat, *, basis):
    if basis!='IN_GAME_WHITE_WITH_PROGRESS':
        raise ValueUnavailable('CharacterPanelBase')
    return ((number(character_base,'CharacterBase',nonnegative=True)+
             number(ark_base,'ArkBase',nonnegative=True)) *
            (1+number(equipment_pp,'ATKPP')/100)+number(flat,'FlatATK'))

def valid_day(value):
    if not isinstance(value,str):
        return False
    try:
        return len(value)==10 and date.fromisoformat(value).isoformat()==value
    except ValueError:
        return False

def resolve_channel(stat_id, mode, *, observation=None, expected_fingerprint=None,
                    ruleset_id=None, comparison_day=None, allow_synthetic=False,
                    atomic_basis=None):
    result={'ActualValue':None, 'ChannelOutcome':'CHANNEL_NO_VALUE'}
    if stat_id in UNSUPPORTED_MODES:
        return {**result,'ChannelOutcome':'NO_VALUE','ErrorCode':'ERR_CHANNEL_MODE_NOT_SUPPORTED_V028'}
    if mode=='ATOMIC' and atomic_basis=='RAW_LEVEL_STAT':
        return {**result,'ErrorCode':'ERR_CHANNEL_CHARACTER_PANEL_BASE_MISSING'}
    if mode!='DIRECT' or not observation:
        return result
    o=observation
    required=('CaptureContext','Provenance','BuildStateFingerprint','RulesetID')
    valid=(stat_id in ('STAT_ATK','STAT_HP','STAT_DEF') and
           all(isinstance(o.get(k),str) and bool(o[k].strip()) for k in required) and
           o.get('BuildStateFingerprint')==expected_fingerprint and
           o.get('RulesetID')==ruleset_id and o.get('StatID')==stat_id and
           o.get('ObservationKind')=='PANEL_TOTAL' and type(o.get('InActiveTeam')) is bool and
           all(o.get('ExternalDeclarations',{}).get(k) for k in EXTERNAL_CLASSES))
    if o.get('InActiveTeam') is True:
        valid=valid and valid_day(o.get('ObservedLocalDate'))
    synthetic=o.get('FixtureType')=='SYNTHETIC_TEST_FIXTURE'
    if synthetic:
        valid=valid and allow_synthetic and o.get('ExecutionEnvironment')=='TEST_HARNESS' and o.get('ProductionEligibility')=='FORBIDDEN'
    if not valid:
        return {**result,'ErrorCode':'ERR_CHANNEL_PANEL_OBSERVATION_CONTEXT_INCOMPLETE'}
    try:
        value=number(o.get('DirectInputValue'),'DirectInputValue',nonnegative=True)
    except ValueUnavailable:
        return {**result,'ErrorCode':'ERR_CHANNEL_PANEL_OBSERVATION_CONTEXT_INCOMPLETE'}
    freshness='UNKNOWN'
    notice=None
    if valid_day(comparison_day) and valid_day(o.get('ObservedLocalDate')):
        freshness='CURRENT' if comparison_day==o['ObservedLocalDate'] else 'DIFFERENT_LOCAL_DAY'
        if freshness!='CURRENT' and o['InActiveTeam']:
            notice='Panelwert evtl. veraltet (Tagesbonus)'
    return {'ActualValue':text(value),'ChannelOutcome':'AVAILABLE','Outcome':'SUCCESS_ASSERTION_MET',
            'ErrorCode':'NONE','NotBlockedByDate':True,'Freshness':freshness,'Notice':notice,
            'Provenance':o['Provenance'],'BuildStateFingerprint':o['BuildStateFingerprint']}
