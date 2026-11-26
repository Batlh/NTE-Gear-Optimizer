import pytest
from nte_gear_optimizer.comparison.decision import DECISION_FIELDS, invalidate_decision
from nte_gear_optimizer.comparison.recommendation import compare, apply_condition
from nte_gear_optimizer.comparison.robust_branches import Branch, evaluate_profile
from nte_gear_optimizer.validation.scoped import Issue
from test_factors import P, values


def cleared(result):
    for field in DECISION_FIELDS:
        assert result[field] is None, (field, result[field])
    assert result['DroveRecommendation'] is False


def test_helper_retains_independent_values_without_mutating_input():
    original = {field: 'stale' for field in DECISION_FIELDS}
    original.update(
        Deltas={'ScaleDirect': '10'},
        GuideReferenceBlock=[{'BeforeAligned': '100', 'DroveRecommendation': True}],
    )
    r = invalidate_decision(original)
    cleared(r)
    assert r['Deltas'] == original['Deltas'] and original['Verdict'] == 'stale'
    assert r['GuideReferenceBlock'][0]['BeforeAligned'] == '100'
    assert not r['GuideReferenceBlock'][0]['DroveRecommendation']


@pytest.mark.parametrize(
    'path',
    [
        'ruleset',
        'layout',
        'binding',
        'conditional',
        'conditional_missing',
        'conditional_nested',
        'affine',
    ],
)
def test_every_late_block_clears_judgment_fields(path):
    if path == 'ruleset':
        r = compare(values(), P, ruleset='UNKNOWN')
    elif path == 'layout':
        r = compare(
            values(),
            P,
            layout_issue=Issue(
                'ERR_LAYOUT_BLOCKED_CELL',
                'BUILD_INVALID_NO_CHANNEL_OUTPUT',
                'Row',
                'Zeile prüfen',
            ),
        )
    elif path == 'binding':
        r = compare(
            values(),
            {**P, 'BuildProfileID': 'p'},
            branches=[Branch('b', {**P, 'BuildProfileID': 'foreign'})],
        )
    elif path == 'conditional_missing':
        r = compare(
            values(),
            P,
            conditional_factors=[{'BeforeFactor': None, 'AfterFactor': '1'}],
        )
    elif path == 'conditional_nested':
        r = compare(
            values(),
            P,
            branches=[Branch('b', P)],
            conditional_factors=[
                {'BeforeFactor': '1', 'AfterFactor': '1'},
                {'BeforeFactor': '2', 'AfterFactor': '1'},
            ],
        )
    elif path == 'affine':
        r = evaluate_profile(
            {
                'BeforeScaleDirect': '3000',
                'AfterScaleDirect': '3020',
                'BeforeShieldPP': '0',
                'AfterShieldPP': '0',
            },
            {'ProfileType': 'SHIELD', 'ScalingStat': 'VER'},
            offset_status='POSITIVE',
            offset_minimum='1000',
            coefficient='0.8',
        )
    else:
        r = compare(
            values(),
            P,
            conditional_factors=[
                {'BeforeFactor': '1', 'AfterFactor': '1'},
                {'BeforeFactor': '2', 'AfterFactor': '1'},
            ],
        )
    cleared(r)
    if path != 'affine':
        assert r['Deltas']['ScaleDirect'] == '10'


def test_external_block_clears_children_but_known_unknown_scenarios_keep_contract_range():
    r = compare(values(), P, branches=[Branch('a', P)], ruleset='UNKNOWN')
    cleared(r)
    cleared(r['BranchEvaluations'][0])
    x = {
        **values(),
        'AfterScaleDirect': '75',
        'CritEligible': 'UNKNOWN',
        'BeforeCritRatePP': '0',
        'AfterCritRatePP': '100',
        'BeforeCritDamagePP': '100',
        'AfterCritDamagePP': '100',
    }
    r = compare(x, P)
    assert r['RatioMin'] == '0.75' and r['RatioMax'] == '1.5'
    # OPB-09's valid uncertainty interval is evidence, not a stale late-block result.
