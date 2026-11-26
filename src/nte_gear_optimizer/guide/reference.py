"""OPB-12..17: sourced guide targets, basis alignment and first changed rank."""

from collections import Counter
from ..numbers import number, text, isolated, ValueUnavailable

PROVENANCE = (
    'BuildProfileID',
    'TargetSetID',
    'TargetVariantID',
    'BranchID',
    'StatID',
    'Unit',
    'TargetLevel',
    'CurrentLevel',
    'ReferenceBasis',
    'Qualifier',
    'Source',
    'RetrievedAtUTC',
    'EvidenceID',
    'MainstatPriorityRank',
    'SubstatPriorityRank',
    'TargetMinimum',
    'TargetMaximum',
)


def decision_rank(row):
    ranks = [row.get(k) for k in ('MainstatPriorityRank', 'SubstatPriorityRank')]
    ranks = [r for r in ranks if type(r) is int and r > 0]
    return min(ranks) if ranks else None


@isolated
def reference(row):
    result = {k: row.get(k) for k in PROVENANCE}
    result.update(
        BeforeAligned=None,
        AfterAligned=None,
        RawDelta=None,
        Trend=None,
        StatusChange=None,
        BeforeAttained=None,
        AfterAttained=None,
        DecisionRank=decision_rank(row),
        DroveRecommendation=False,
        ReferenceUnavailableReason=None,
    )
    try:
        b = number(row.get('BeforeValue'), 'BeforeValue')
        a = number(row.get('AfterValue'), 'AfterValue')
        result['RawDelta'] = text(a - b)
        basis = row.get('ReferenceBasis')
        if (
            not basis
            or row.get('ContextVerified') is not True
            or not row.get('Source')
            or not (row.get('EvidenceID') or row.get('RetrievedAtUTC'))
        ):
            result['ReferenceUnavailableReason'] = 'BASIS_UNVERIFIED'
            return result
        if row.get('CurrentLevel') is None or row.get('CurrentLevel') != row.get(
            'TargetLevel'
        ):
            result['ReferenceUnavailableReason'] = 'BASIS_UNVERIFIED'
            return result
        same = row.get('BeforeBasis') == basis and row.get('AfterBasis') == basis
        if not same:
            if not (
                row.get('BonusTransform') == 'ADDITIVE_SAME_UNIT'
                and row.get('StatUnit')
                and row.get('StatUnit') == row.get('ExcludedBonusUnit')
                and row.get('ExcludedBonusSource')
                and row.get('BeforeBasis')
                and row.get('AfterBasis')
            ):
                result['ReferenceUnavailableReason'] = 'BASIS_UNVERIFIED'
                return result
            b -= number(row.get('BeforeExcludedBonus'), 'BeforeExcludedBonus')
            a -= number(row.get('AfterExcludedBonus'), 'AfterExcludedBonus')
        result.update(BeforeAligned=text(b), AfterAligned=text(a))
        minimum = number(row.get('TargetMinimum'), 'TargetMinimum')
        attained_b, attained_a = b >= minimum, a >= minimum
        distance_b, distance_a = max(minimum - b, 0), max(minimum - a, 0)
        trend = (
            'CLOSER'
            if distance_a < distance_b
            else 'FARTHER'
            if distance_a > distance_b
            else 'EQUAL'
        )
        change = (
            'GAINED'
            if not attained_b and attained_a
            else 'LOST'
            if attained_b and not attained_a
            else 'UNCHANGED'
        )
        result.update(
            BeforeAttained=attained_b,
            AfterAttained=attained_a,
            Trend=trend,
            StatusChange=change,
            BeforeDistance=text(distance_b),
            AfterDistance=text(distance_a),
        )
    except ValueUnavailable as exc:
        result['ReferenceUnavailableReason'] = str(exc)
    return result


def rank_verdict(references):
    changed = [
        r
        for r in references
        if r['StatusChange'] in ('GAINED', 'LOST') and r['DecisionRank'] is not None
    ]
    if not changed:
        return {
            'OutputStatus': 'NICHT_ENTSCHEIDBAR',
            'Verdict': None,
            'DroveRecommendation': False,
        }
    rank = min(r['DecisionRank'] for r in changed)
    if any(
        r['ReferenceUnavailableReason']
        and (r['DecisionRank'] is None or r['DecisionRank'] <= rank)
        for r in references
    ):
        return {
            'OutputStatus': 'INDETERMINATE_MISSING_DEPENDENCY',
            'Verdict': None,
            'DroveRecommendation': False,
        }
    selected = [r for r in changed if r['DecisionRank'] == rank]
    changes = {r['StatusChange'] for r in selected}
    verdict = (
        'BETTER' if changes == {'GAINED'} else 'WORSE' if changes == {'LOST'} else None
    )
    for r in selected:
        r['DroveRecommendation'] = True
    return {
        'OutputStatus': 'READY' if verdict else 'NICHT_ENTSCHEIDBAR',
        'Verdict': verdict,
        'DroveRecommendation': True,
        'DecisionRank': rank,
    }


def quarantine_optional_targets(rows):
    """Pure relation check only: no package import, migration or commit engine."""
    ids = Counter(r.get('UserComparisonTargetID') for r in rows)

    def key(r):
        return tuple(
            r.get(k)
            for k in ('BuildStateID', 'StatID', 'TargetSetID', 'TargetVariantID')
        )

    keys = Counter(key(r) for r in rows)
    bad = [
        r
        for r in rows
        if not r.get('UserComparisonTargetID')
        or ids[r['UserComparisonTargetID']] > 1
        or keys[key(r)] > 1
    ]
    good = [r for r in rows if r not in bad]
    return good, bad


def condition(condition, state, *, domains):
    """Explicit domain and operator evaluation; invalid config is not FALSE."""
    field = condition.get('Field')
    required = condition.get('RequiredValue')
    op = condition.get('Operator')
    if (
        field not in domains
        or required not in domains[field]
        or state.get(field) not in domains[field]
    ):
        return None
    actual = state[field]
    if op == '=':
        return actual == required
    if op == '>=':
        if field not in ('Awakening', 'ArkAdvancement'):
            return None
        order = domains[field]
        return order.index(actual) >= order.index(required)
    return None


def select_target(base, variants, state, *, domains):
    matches = []
    for row in variants:
        outcomes = [
            condition(c, state, domains=domains) for c in row.get('Conditions', ())
        ]
        if None in outcomes:
            return None
        if all(outcomes):
            matches.append(row)
    if not matches:
        return base
    if any(
        type(r.get('Priority')) is not int or type(r.get('Specificity')) is not int
        for r in matches
    ):
        return None
    priority = max((r['Priority'], r['Specificity']) for r in matches)
    winners = [r for r in matches if (r['Priority'], r['Specificity']) == priority]
    return winners[0] if len(winners) == 1 else None
