"""Synthetic setup adapter for the frozen 1B-0 vectors (not production logic).

Case IDs choose fixture records only. Expected values are never used to compute
results. The production modules do not know CaseID or FixtureAktion.
"""

from nte_gear_optimizer.comparison.recommendation import compare
from nte_gear_optimizer.comparison.robust_branches import Branch
from nte_gear_optimizer.models.profile_state import unique_reference, build_items_valid
from nte_gear_optimizer.validation.scoped import layout, ark_progress
from nte_gear_optimizer.panels.resolution import resolve_channel
from nte_gear_optimizer.projection.lv80 import project

RELEASE = {
    'ProfileType': 'DAMAGE',
    'ScalingStat': 'ANG',
    'CritEligible': 'FALSE',
    'BreakEligible': 'FALSE',
    'CycleType': 'NONE',
}
MASK = {(r, c) for r in range(1, 6) for c in range(1, 6)} - {
    (1, 3),
    (4, 1),
    (4, 5),
    (5, 1),
    (5, 5),
}


def target(**kwargs):
    return {
        'BuildProfileID': 'SYN_PROFILE',
        'StatID': 'SYN_STAT',
        'TargetMinimum': '100',
        'BeforeValue': '90',
        'AfterValue': '110',
        'ReferenceBasis': 'PANEL',
        'BeforeBasis': 'PANEL',
        'AfterBasis': 'PANEL',
        'TargetLevel': 80,
        'CurrentLevel': 80,
        'Unit': 'FLAT',
        'ContextVerified': True,
        'Source': 'SYNTHETIC_TEST_FIXTURE',
        'EvidenceID': '1B0-contract-vector',
        'SubstatPriorityRank': 2,
        **kwargs,
    }


def run_case(case):
    case_id = case['CaseID']
    x = dict(case['Inputs'])
    opts = {}
    if case_id == 'KP01_UNUSED_BAD_MASTER':
        registry = [{'ID': 'valid', 'Profile': RELEASE}, {'ID': 'unused', 'QA': 'FAIL'}]
        release = unique_reference(registry, 'ID', 'valid')['Profile']
    else:
        release = RELEASE
    if case_id == 'KP01_SHARED_ITEM_PLANS':
        assert build_items_valid(['shared']) and build_items_valid(['shared'])
    if case_id == 'KP02_MISSING_ARK_PROGRESS':
        opts['ark_issue'] = ark_progress(None, 20, {0: 20})
    if case_id == 'KP03_BASELINE_SWAP':
        opts['targets'] = [
            target(
                **{
                    k: v
                    for k, v in x.items()
                    if k in ('BeforeValue', 'AfterValue', 'TargetMinimum', 'StatID')
                }
            )
        ]
    if case_id == 'KP06_FIRST_CHANGED_RANK':
        opts['targets'] = [
            {
                **target(),
                'SubstatPriorityRank': 1,
                'TargetMinimum': '50',
                'BeforeValue': '60',
                'AfterValue': '60',
            },
            target(),
        ]
    if case_id == 'KP06_RANK_CONFLICT':
        opts['targets'] = [
            target(),
            {**target(), 'BeforeValue': '110', 'AfterValue': '90'},
        ]
    if case_id == 'KP06_BASIS_CONVERSION':
        opts['targets'] = [{**target(), **x}]
    if case_id == 'KP08_BRANCH_OVERRIDE_BOUND':
        x['CritEligible'] = 'TRUE'
        opts['branches'] = [Branch('SYNTHETIC_BRANCH_B', RELEASE)]
    if case_id in ('KP08_BRANCHES_DISAGREE', 'KP08_BRANCH_MISSING'):
        opts['branches'] = [
            Branch('SYN_A', RELEASE),
            Branch(
                'SYN_B',
                RELEASE,
                {'AfterScaleDirect': '90' if case_id.endswith('DISAGREE') else None},
            ),
        ]
        opts['expected_branch_ids'] = ['SYN_A', 'SYN_B']
    if case_id.startswith('KP08_AFFINE_'):
        branch_id = x.get('SelectedBranchID') or 'SYNTHETIC_ADLER_SHIELD_BRANCH'
        p = {**RELEASE, 'ProfileType': 'SHIELD', 'ScalingStat': 'VER'}
        branches = [
            Branch(
                branch_id,
                p,
                offset_status='POSITIVE',
                offset_minimum=x['FixedOffsetMinimum'],
                coefficient=x['ScalingCoefficientLevel1'],
            )
        ]
        if case_id == 'KP08_AFFINE_NEAR':
            branches.append(Branch('SYN_OTHER', p, offset_status='UNKNOWN'))
        opts['branches'] = branches
    layout_issue = None
    if case_id.startswith('KP12_'):
        cell = {
            'KP12_BLOCKED': (1, 3),
            'KP12_OUTSIDE': (6, 1),
            'KP12_AXIS_ORACLE': (3, 1),
        }[case_id]
        layout_issue = layout(['SYN_ITEM'], [{'cells': [cell]}], MASK)
        opts['layout_issue'] = layout_issue
    if case_id == 'KP04_CONDITIONAL_REVERSAL':
        opts['conditional_factors'] = [
            {'BeforeFactor': '1', 'AfterFactor': '1'},
            {'BeforeFactor': '1.2', 'AfterFactor': '1'},
        ]
    if case_id == 'KP06_OPTIONAL_TARGET_COLLISION':
        row = {
            'UserComparisonTargetID': 'COLLISION',
            'BuildStateID': 'SYN_BUILD',
            'StatID': 'SYN_STAT',
            'TargetSetID': 'SYN_SET',
            'TargetVariantID': 'SYN_VARIANT',
        }
        opts['optional_targets'] = [row, {**row, 'StatID': 'OTHER'}]
    result = compare(x, release, **opts)
    if case_id == 'KP12_AXIS_ORACLE':
        result['LayoutValid'] = layout_issue is None
    if case_id.startswith('KP07_'):
        result.update(project(x))
    if case_id.startswith(
        (
            'KP09_CONTEXT_',
            'KP09_CANDIDATE_',
            'KP10_MODE_',
            'KP11_ATOMIC_',
            'KP09_DIRECT_VALID_',
        )
    ) or case_id in ('KP09_TEAM_STALE_WARNING', 'KP09_COMPARISON_DATE_MISSING'):
        atomic = case_id.startswith('KP11_ATOMIC_')
        observation = x if 'DirectInputValue' in x else None
        if case_id.startswith('KP09_CONTEXT_'):
            observation = {
                'StatID': x['StatID'],
                'BuildStateFingerprint': 'MATCHED',
                'RulesetID': 'R',
                'DirectInputValue': '1234',
            }
        result.update(
            resolve_channel(
                x['StatID'],
                'ATOMIC' if atomic else 'DIRECT',
                observation=observation,
                expected_fingerprint=x.get('BuildStateFingerprint', 'MATCHED'),
                ruleset_id=x.get('RulesetID', 'R'),
                comparison_day=x.get('ComparisonLocalDate'),
                allow_synthetic=True,
                atomic_basis=x.get('WhiteBasis'),
            )
        )
    return result


def expected_field(result, key):
    if key == 'BranchEvaluations.AffineStatus':
        return [b['AffineStatus'] for b in result.get('BranchEvaluations', [])]
    return result.get(key)


def check_case(case, result):
    for key, expected in case['Expected'].items():
        actual = expected_field(result, key)
        if key == 'BranchEvaluations.AffineStatus':
            assert expected in actual, (case['CaseID'], key, expected, actual)
        else:
            assert actual == expected, (case['CaseID'], key, expected, actual)
