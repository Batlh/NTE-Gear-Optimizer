"""Historical references must not become rules or block independent comparisons."""

from copy import deepcopy
import csv
import hashlib
import io
import json
from pathlib import Path

import pytest

from nte_gear_optimizer_app.catalog import load_catalog
from nte_gear_optimizer_app.legacy_reference import (
    STATUS,
    REFERENCE_GROUPS,
    ReferenceIntegrityError,
    ark_display_name,
    filter_arks,
    load_extended_catalog,
    load_reference,
    merge_reference_catalog,
    validate_reference,
)
from nte_gear_optimizer_app.viewmodel import ComparisonViewModel

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/legacy_v028_import'
ASSETS = ROOT / 'src/nte_gear_optimizer_app/assets'


def ready(catalog):
    vm = ComparisonViewModel(catalog=catalog)
    vm.choose_character('ELYMS')
    for k, v in {
        'ProfileType': 'DAMAGE',
        'ScalingStat': 'ANG',
        'CritEligible': 'FALSE',
        'BreakEligible': 'FALSE',
        'CycleType': 'NONE',
    }.items():
        vm.set_override(k, v)
    for group in vm.groups():
        vm.zero_group(group)
    for group in vm.groups(parts=True):
        vm.zero_group(group, parts=True)
    vm.set_value('current', 'ScaleDirect', '100')
    vm.set_value('x', 'ScaleDirect', '10')
    vm.set_value('y', 'ScaleDirect', '20')
    return vm


def test_actual_reference_counts_and_unchanged_two_ark_baseline():
    base = load_catalog()
    before = deepcopy(base)
    reference = load_reference()
    merged = merge_reference_catalog(base, reference)
    assert len(reference['Arks']) == 49 and len(reference['Sets']) == 12
    assert len(merged['Arks']) == 51 and len(base['Arks']) == 2
    assert reference['Counts']['ExplicitModuleArrayValues'] == 378
    assert reference['Counts']['CartridgeLevels'] == 63
    assert base == before
    assert {
        k: v
        for k, v in merged.items()
        if k not in ('Arks', 'LegacyReference', 'LegacyReferenceWarning')
    } == {k: v for k, v in base.items() if k != 'Arks'}


def test_every_tsv_observation_matches_original_source_row_and_hash():
    reference = load_reference()
    for group in REFERENCE_GROUPS:
        for row in reference[group]:
            path = DATA / 'source' / row['SourceRelativePath']
            raw = path.read_bytes()
            assert hashlib.sha256(raw).hexdigest().upper() == row['SourceSHA256']
            source = list(
                csv.DictReader(io.StringIO(raw.decode('utf-8')), delimiter='\t')
            )
            assert row['Original'] == source[row['SourceRow'] - 2]
            assert row['DataStatus'] == STATUS


def test_dataset_and_application_copy_are_identical_and_manifest_bound():
    assert (DATA / 'reference.json').read_bytes() == (
        ASSETS / 'legacy_v028_reference.json'
    ).read_bytes()
    rows = list(
        csv.DictReader(
            io.StringIO((DATA / 'MANIFEST.tsv').read_text(encoding='utf-8')),
            delimiter='\t',
        )
    )
    for row in rows:
        raw = (DATA / row['RelativePath']).read_bytes()
        assert len(raw) == int(row['Bytes'])
        assert hashlib.sha256(raw).hexdigest().upper() == row['SHA256']


@pytest.mark.parametrize(
    'change',
    [
        'duplicate_ark',
        'duplicate_record',
        'status',
        'source',
        'automatic_winner',
        'effect_reference',
        'array_length',
    ],
)
def test_invalid_reference_is_not_accepted(change):
    data = deepcopy(load_reference())
    if change == 'duplicate_ark':
        data['Arks'][1]['ArkID'] = data['Arks'][0]['ArkID']
    elif change == 'duplicate_record':
        data['ArkExactPoints'][1]['RecordID'] = data['ArkExactPoints'][0]['RecordID']
    elif change == 'status':
        data['Arks'][0]['DataStatus'] = 'CURRENT'
    elif change == 'source':
        data['ModuleEndpoints'][0]['SourceSHA256'] = '0' * 64
    elif change == 'automatic_winner':
        data['ArkExactPoints'][0]['Original']['AutomaticWinner'] = 'TRUE'
    elif change == 'effect_reference':
        data['Sets'][0]['EffectRecordIDs'].append('UNRELATED_RECORD')
    else:
        data['ModuleLevelSeries'][0]['Original']['ValueSequence_L0_to_L20'] = '1,2'
    with pytest.raises(ReferenceIntegrityError):
        validate_reference(data)


def test_current_patch_identity_wins_without_mutating_either_input():
    reference = load_reference()
    old = reference['Arks'][0]
    # Deliberately overlapping fixture, not a fabricated production value.
    base = {
        'Arks': [
            {
                'ArkID': old['ArkID'],
                'ArkName': 'Current patch fixture',
                'ArkType': old['ArkType'],
                'DataStatus': 'CURRENT_FIXTURE',
            }
        ]
    }
    before = deepcopy(base)
    merged = merge_reference_catalog(base, reference)
    actual = next(r for r in merged['Arks'] if r['ArkID'] == old['ArkID'])
    assert actual == before['Arks'][0] and base == before
    assert reference['Arks'][0]['ArkName'] == old['ArkName']


def test_renaming_display_name_never_regenerates_an_identity():
    reference = deepcopy(load_reference())
    old_ids = {r['ArkID'] for r in reference['Arks']}
    chosen = reference['Arks'][0]['ArkID']
    reference['Arks'][0]['ArkName'] = 'Umbenannte Anzeige – unveränderte ID'
    merged = merge_reference_catalog(load_catalog(), reference)
    assert {r['ArkID'] for r in reference['Arks']} == old_ids
    assert (
        next(r for r in merged['Arks'] if r['ArkID'] == chosen)['ArkName']
        == 'Umbenannte Anzeige – unveränderte ID'
    )


def test_no_character_mapping_shows_all_arks_with_visible_type_and_status():
    catalog = load_extended_catalog()
    filtered, state = filter_arks(catalog['Arks'], 'ELYMS', [])
    assert (
        filtered == catalog['Arks'] and state == 'NO_VERIFIED_CHARACTER_TYPE_SHOW_ALL'
    )
    legacy = next(r for r in filtered if r.get('DataStatus') == STATUS)
    assert legacy['ArkType'] in ark_display_name(legacy)
    assert '1.4 ungeprüft' in ark_display_name(legacy)


def test_future_filter_requires_real_sourced_mapping_and_never_infers_guide_type():
    arks = load_extended_catalog()['Arks']
    unsourced = [
        {
            'CharacterID': 'ELYMS',
            'ArkType': 'Solid',
            'SourceKind': 'GUIDE_RECOMMENDATION',
            'SourceEvidence': 'recommendation fixture',
        }
    ]
    assert filter_arks(arks, 'ELYMS', unsourced)[0] == arks
    sourced = [
        {
            'CharacterID': 'ELYMS',
            'ArkType': 'Solid',
            'SourceKind': 'USER_INGAME',
            'SourceEvidence': 'ingame test fixture, not production data',
        }
    ]
    filtered, status = filter_arks(arks, 'ELYMS', sourced)
    assert status == 'SOURCED_TYPE_FILTER' and filtered
    assert all(r['ArkType'] == 'Solid' for r in filtered)
    assert filter_arks(arks, 'ANOTHER_CHARACTER', sourced)[0] == arks
    ambiguous = sourced + [{**sourced[0], 'ArkType': 'Gas'}]
    assert filter_arks(arks, 'ELYMS', ambiguous)[0] == arks


def test_missing_optional_reference_never_blocks_independent_manual_comparison(
    tmp_path,
):
    catalog = load_extended_catalog(tmp_path)
    assert len(catalog['Arks']) == 2 and catalog['LegacyReferenceWarning']
    result = ready(catalog).calculate()
    assert result['engine']['Verdict'] == 'BETTER'
    assert result['engine']['RawRatio'] == '1.1'


def test_corrupted_asset_hash_cannot_supply_reference_values(tmp_path):
    for name in ('legacy_v028_reference.json', 'legacy_v028_reference_manifest.json'):
        (tmp_path / name).write_bytes((ASSETS / name).read_bytes())
    path = tmp_path / 'legacy_v028_reference.json'
    with path.open('ab') as stream:
        stream.write(b' ')
    with pytest.raises(ReferenceIntegrityError, match='hash'):
        load_reference(tmp_path)
    catalog = load_extended_catalog(tmp_path)
    assert catalog['LegacyReference'] is None
    assert ready(catalog).calculate()['engine']['Verdict'] == 'BETTER'


def test_legacy_selection_and_unbound_values_do_not_change_the_engine():
    base = ready(load_catalog()).calculate()
    merged = load_extended_catalog()
    vm = ready(merged)
    old = merged['LegacyReference']['Arks'][0]['ArkID']
    vm.choose_ark(old)
    vm.ark_level = '80'
    # Raw references are intentionally not prefills or engine factors.
    merged['LegacyReference']['ArkExactPoints'][0]['Original']['MainStatValue'] = (
        'unresolved observation'
    )
    actual = vm.calculate()
    assert actual['engine'] == base['engine']
    assert actual['part_deltas'] == base['part_deltas']


def test_ranking_identity_gaps_remain_explicit_without_invented_arks():
    data = load_reference()
    ranking = data['GuideRankingMappings']
    assert len(ranking['rows']) == 54 and ranking['matched'] == 52
    assert len(ranking['unresolved']) == 2
    assert {r['ArkName'] for r in ranking['unresolved']} == {'Far Side of the Moon'}
    assert all(r['ArkName'] != 'Far Side of the Moon' for r in data['Arks'])
    missing_time = [
        r
        for g in REFERENCE_GROUPS
        for r in data[g]
        if r['SourceRetrievedAt']['Status'] == 'NOT_DECLARED_IN_SOURCE'
    ]
    assert missing_time and all(
        r['SourceRetrievedAt']['Value'] is None for r in missing_time
    )
