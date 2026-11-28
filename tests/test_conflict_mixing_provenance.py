"""Known source dates and contract references are not numerical engine rules."""

from copy import deepcopy
from datetime import datetime, timedelta

import pytest

from nte_gear_optimizer_app.legacy_reference import (
    load_reference,
    validate_reference,
    ReferenceIntegrityError,
)
from nte_gear_optimizer_app.reference_view import reference_sections


def test_both_excluded_conflicts_have_source_date_from_same_frozen_workbook():
    doc = load_reference()
    rows = doc['ArkConflictObservations']
    assert len(rows) == 2
    for row in rows:
        date = row['SourceRetrievedAt']
        assert date['OriginalExcelSerial'] == '46269'
        assert (
            date['Value']
            == (datetime(1899, 12, 30) + timedelta(days=46269)).date().isoformat()
        )
        assert date['Status'] == 'DECLARED_SOURCE_DATE_1900_SERIAL'
        assert date['SourceSheet'] == 'Data_Sources' and date['SourceRow'] >= 2
        assert row['SourceRole'] == 'RAW_CONFLICT_OBSERVATION_NONOPERATIVE'
        assert (
            row['Original']['ScoringEnabled'] == '0'
            and row['Original']['IncludeInStaticStats'] == '0'
        )
        assert row['Original']['VerificationStatus'] == 'CONFLICT'
    assert [r['Original']['EffectText'] for r in rows] == [
        'DEF Ignore duration observation: 70s',
        'DEF Ignore duration observation: 3s',
    ]


@pytest.mark.parametrize('mutation', ['date', 'role', 'scoring', 'static', 'identity'])
def test_invalid_conflict_provenance_or_activation_is_rejected(mutation):
    doc = deepcopy(load_reference())
    row = doc['ArkConflictObservations'][0]
    if mutation == 'date':
        del row['SourceRetrievedAt']
    elif mutation == 'role':
        row['SourceRole'] = 'OPERATIVE_GAME_DATA'
    elif mutation == 'scoring':
        row['Original']['ScoringEnabled'] = '1'
    elif mutation == 'static':
        row['Original']['IncludeInStaticStats'] = '1'
    else:
        row['Original']['ArkID'] = 'UNKNOWN'
    with pytest.raises(ReferenceIntegrityError):
        validate_reference(doc)


def test_all_six_exact_contract_rows_are_retained_as_references_not_interpolated_tiers():
    doc = load_reference()
    rows = doc['ArkMixingContract']
    assert len(rows) == doc['Counts']['ArkMixingContractRows'] == 6
    assert {r['Original']['Field'] for r in rows} == {
        'Alternatives',
        'ConsumedCopy',
        'RetainedCopy',
        'ObservedEvidence',
        'PassiveValue',
        'Maximum',
    }
    assert all(
        r['SourceRetrievedAt']['Value']
        and r['SourceRetrievedAt']['Kind'] == 'ReadAtUTC'
        for r in rows
    )
    sections = reference_sections(doc)
    mixed = next(rows for key, _, rows in sections if key == 'mixing')
    assert len(mixed) == 6
    rendered = {key: text for key, _, text in mixed}
    for row in rows:
        text = rendered[row['RecordID']]
        assert (
            row['Original']['Rule'] in text
            and row['Original']['MissingTreatment'] in text
        )
        assert (
            'keine vollständige Wertetabelle' in text
            and 'wird nicht in die Berechnung übernommen' in text
        )
        assert row['SourceSHA256'] in text


def test_mixing_contract_count_mismatch_is_rejected():
    doc = load_reference()
    doc['Counts']['ArkMixingContractRows'] = 5
    with pytest.raises(ReferenceIntegrityError):
        validate_reference(doc)
