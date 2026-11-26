"""Scoped validation, N5D error dictionary and console phase precedence.

Callers supply released geometry/progression records; no character mask default.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class Issue:
    code: str
    outcome: str
    field: str
    help: str

def integer(value, low, high):
    return type(value) is int and low <= value <= high

def ark_progress(stage, level, caps):
    if not integer(stage, 0, 6):
        return Issue('ERR_STATE_ARK_ASCENSION_INVALID', 'ARK_INSTANCE_NO_DEPENDENT_OUTPUT',
                     'ArkAscensionStage', 'Ark-Stufe fehlt oder liegt nicht zwischen 0 und 6')
    if stage not in caps or (stage and stage-1 not in caps):
        return None, 'UNKNOWN'
    floor = 1 if stage == 0 else caps[stage-1]
    if not integer(level, floor, caps[stage]):
        # N5D cap error applies to above-cap; below-floor has no invented ID.
        if type(level) is int and level > caps[stage]:
            return Issue('ERR_STATE_ARK_LEVEL_EXCEEDS_ASCENSION_CAP', 'ARK_INSTANCE_NO_DEPENDENT_OUTPUT',
                         'ArkLevel', 'Ark-Level überschreitet die freigeschaltete Grenze')
        if type(level) is int and level < floor:
            return Issue('ERR_STATE_ARK_LEVEL_BELOW_ASCENSION_FLOOR', 'ARK_INSTANCE_NO_DEPENDENT_OUTPUT',
                         'ArkLevel', 'Ark-Level liegt unter der Stufengrenze')
        return None, 'UNKNOWN'
    return None, 'AVAILABLE'

def resonance(awakening):
    if not integer(awakening, 0, 6):
        return None
    return () if awakening < 3 else ('R3',) if awakening < 6 else ('R3','R6')

def character_level_valid(level):
    return integer(level, 1, 80)

def layout(assigned_ids, placements, usable_cells, *, mask_matches=True):
    """Module count precedes geometry. All assigned IDs count, even unplaced."""
    def fail(code, field):
        return Issue(code,'BUILD_INVALID_NO_CHANNEL_OUTPUT',field,'Konsole prüfen: '+field)
    if not 0 <= len(assigned_ids) <= 10:
        return fail('ERR_LAYOUT_MODULE_COUNT_INVALID','EquippedModuleInstanceCount')
    if usable_cells is None:
        return fail('ERR_LAYOUT_MASK_REQUIRED','CharacterMask')
    if not mask_matches:
        return fail('ERR_LAYOUT_CHARACTER_MASK_MISMATCH','CharacterMask')
    cells = [tuple(cell) for p in placements for cell in p['cells']]
    if any(not all(type(n) is int and 1 <= n <= 5 for n in cell) or len(cell)!=2 for cell in cells):
        return fail('ERR_LAYOUT_OUT_OF_BOUNDS','Row/Column')
    if any(cell not in usable_cells for cell in cells):
        return fail('ERR_LAYOUT_BLOCKED_CELL','Row/Column')
    if len(cells) != len(set(cells)):
        return fail('ERR_LAYOUT_OVERLAP','Row/Column')
    if any(p.get('rotation',0)!=0 or p.get('reflected',False) for p in placements):
        return fail('ERR_LAYOUT_TRANSFORM_NOT_ALLOWED','Transformation')
    return None


def validate_selected(records, key, selected, validators, expected_checks):
    """Compute coverage from actual validators, not persisted QA strings."""
    from ..models.profile_state import unique_reference
    row=unique_reference(records,key,selected)
    if row is None:return {'Status':'FAIL','Field':key,'Checks':{}}
    results={name:validators[name](row) if callable(validators.get(name)) else None for name in expected_checks}
    status='FAIL' if any(v is False for v in results.values()) else 'UNKNOWN' if not results or any(v is not True for v in results.values()) else 'PASS'
    return {'Status':status,'Checks':results}

def character_state(row, *, allowed_slots):
    """Typed axes stay separate; null does not imply zero or all slots."""
    checks={'Level':character_level_valid(row['Level']) if row.get('Level') is not None else None,
            'AwakeningStage':integer(row['AwakeningStage'],0,6) if row.get('AwakeningStage') is not None else None}
    slots=row.get('AwakeningEffectSelection')
    checks['AwakeningEffectSelection']=None
    if slots is not None and checks['AwakeningStage'] is True:
        checks['AwakeningEffectSelection']=(isinstance(slots,(list,tuple,set,frozenset)) and
            len(slots)==len(set(slots))==row['AwakeningStage'] and all(s in allowed_slots for s in slots))
    return checks

def item_stats(rows, *, kind, level, stat_units, permitted_main_ids, limits):
    """N4_2 owner rows; actual values only, no inferred mainstat or curve.

    limits is the exact released (role,slot,stat) -> (min,max) point for this
    item type/rarity/level. Missing source points stay UNKNOWN.
    """
    from ..numbers import number, ValueUnavailable
    if type(level) is not int:return {'Status':'UNKNOWN','Field':'Level'}
    if kind not in ('MODULE','CARTRIDGE'):return {'Status':'UNKNOWN','Field':'ItemType'}
    mains=[r for r in rows if r.get('Role')=='MAIN']
    wanted=2 if kind=='MODULE' else 1
    if len(mains)!=wanted:return {'Status':'FAIL','Field':'MainStats'}
    main_ids=[r.get('StatID') for r in mains]
    if kind=='MODULE' and set(main_ids)!={'STAT_ATK','STAT_HP'}:return {'Status':'FAIL','Field':'MainStats'}
    if kind=='CARTRIDGE' and main_ids[0] not in permitted_main_ids:return {'Status':'FAIL','Field':'MainStatID'}
    expected_slots={slot for slot in range(1,5) if level>=5*slot}
    present_slots={r.get('Slot') for r in rows if r.get('Role')=='SUB'}
    if not expected_slots.issubset(present_slots):return {'Status':'UNKNOWN','Field':'SubStats'}
    if kind=='CARTRIDGE' and mains[0].get('Slot')!=1:return {'Status':'FAIL','Field':'MainStats'}
    seen=set();unknown=False
    for row in rows:
        role,slot,stat=row.get('Role'),row.get('Slot'),row.get('StatID')
        if role not in ('MAIN','SUB') or type(slot) is not int:return {'Status':'FAIL','Field':'Role/Slot'}
        identity=(role,slot)
        if identity in seen:return {'Status':'FAIL','Field':'Role/Slot'}
        seen.add(identity)
        if role=='SUB' and not integer(slot,1,4):return {'Status':'FAIL','Field':'Slot'}
        if stat not in stat_units or row.get('Unit')!=stat_units[stat]:return {'Status':'FAIL','Field':'Unit'}
        if role=='SUB' and level<5*slot:
            # A stored future roll is retained, but not an active contribution.
            continue
        try:value=number(row.get('Value'),'Value',nonnegative=True)
        except ValueUnavailable as exc:
            if exc.invalid:return {'Status':'FAIL','Field':'Value'}
            unknown=True;continue
        point=limits.get((role,slot,stat))
        if point is None:unknown=True;continue
        low,high=point
        if not number(low)<=value<=number(high):return {'Status':'FAIL','Field':'Value'}
    return {'Status':'UNKNOWN' if unknown else 'PASS',
            'ActiveSubstats':[r for r in rows if r.get('Role')=='SUB' and level>=5*r['Slot']]}
