from nte_gear_optimizer.models.profile_state import (
    effective_profile,
    unique_reference,
    build_items_valid,
    ruleset_status,
)


def test_null_unknown_invalid_and_separate_domains():
    release = {'ProfileType': 'HEAL', 'ScalingStat': 'LP', 'CritEligible': 'FALSE'}
    p = effective_profile(release, {'CritEligible': None})
    assert (
        p.values['CritEligible'] == 'FALSE' and p.sources['CritEligible'] == 'RELEASE'
    )
    p = effective_profile(release, {'CritEligible': 'UNKNOWN', 'ScalingStat': 'HEAL'})
    assert p.values['CritEligible'] == 'UNKNOWN' and p.sources['CritEligible'] == 'USER'
    assert p.values['ProfileType'] == 'HEAL' and p.values['ScalingStat'] == 'LP'
    assert p.diagnostics == ('Ungültiger optionaler Wert: ScalingStat',)


def test_branch_boundary_and_unrelated_record():
    p = effective_profile(
        {'CritEligible': 'FALSE'},
        {'CritEligible': 'TRUE'},
        branch_id='B',
        override_branch_id='A',
    )
    assert (
        p.values['CritEligible'] == 'FALSE' and p.sources['CritEligible'] == 'RELEASE'
    )
    assert unique_reference(
        [{'ID': 'good'}, {'ID': 'bad', 'QA': 'FAIL'}], 'ID', 'good'
    ) == {'ID': 'good'}
    assert unique_reference([{'ID': 'good'}, {'ID': 'good'}], 'ID', 'good') is None


def test_build_reuse_is_not_ownership():
    assert build_items_valid(['shared']) and build_items_valid(['shared'])
    assert not build_items_valid(['shared', 'shared'])


def test_ruleset_exact_revision_and_unknown():
    rows = [{'RulesetID': 'R', 'Revision': '1', 'Status': 'SUPERSEDED'}]
    assert ruleset_status(rows, 'R', '1') == 'SUPERSEDED'
    assert ruleset_status(rows, 'R', 1) == 'UNKNOWN'


def test_mutants_branch_leak_global_gate_and_domain_confusion_are_killed():
    release = {'CritEligible': 'FALSE', 'ProfileType': 'SHIELD', 'ScalingStat': 'VER'}
    expected = effective_profile(
        release, {'CritEligible': 'TRUE'}, branch_id='B', override_branch_id='A'
    )
    # These deliberately wrong algorithms disagree with the contract oracle.
    assert {**release, **{'CritEligible': 'TRUE'}} != expected.values
    assert ('FAIL' not in ['FAIL']) is not (
        unique_reference([{'ID': 'x'}, {'QA': 'FAIL'}], 'ID', 'x') is not None
    )
    assert (
        'SHIELD'
        not in __import__(
            'nte_gear_optimizer.models.profile_state', fromlist=['DOMAINS']
        ).DOMAINS['ScalingStat']
    )
