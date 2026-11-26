"""Frozen v0.28 ScoringRules: heuristic item fit and roll quality, not DPS.

The caller supplies released weights, exact roll baselines/ranges and policy.
Ark progress and unrelated build state are intentionally not dependencies.
"""

from ..numbers import number, text, isolated, ValueUnavailable


@isolated
def score_item(
    rolls, weights, policy, *, required_slots, main_stat_id=None, main_weights=None
):
    out = {
        'Status': 'UNKNOWN',
        'Relevance': None,
        'Quality': None,
        'Overall': None,
        'Recommendation': None,
    }
    try:
        if len(rolls) != required_slots:
            raise ValueUnavailable('Substats')
        ids = [r.get('StatID') for r in rolls]
        if None in ids or len(ids) != len(set(ids)):
            raise ValueUnavailable('SubstatID', True)
        all_weights = {
            k: number(v, 'Weight:' + k, nonnegative=True) for k, v in weights.items()
        }
        selected = sum(all_weights[k] for k in ids)
        best = sum(sorted(all_weights.values(), reverse=True)[:required_slots])
        if main_weights is not None:
            if main_stat_id is None:
                raise ValueUnavailable('MainStatID')
            mw = {
                k: number(v, 'MainWeight:' + k, nonnegative=True)
                for k, v in main_weights.items()
            }
            selected += mw[main_stat_id]
            best += max(mw.values())
        if best <= 0:
            raise ValueUnavailable('Weights')
        ratios = []
        for r in rolls:
            val = number(r.get('Value'), 'Value', nonnegative=True)
            baseline = number(r.get('Baseline'), 'Baseline', nonnegative=True)
            lo = number(r.get('Minimum'), 'Minimum', nonnegative=True)
            hi = number(r.get('Maximum'), 'Maximum', nonnegative=True)
            if baseline <= 0 or not lo <= val <= hi:
                raise ValueUnavailable('Value', True)
            ratios.append(val / baseline)
        if not ratios:
            raise ValueUnavailable('Rolls')
        cap = number(policy.get('Maximum score'), 'Maximum score', nonnegative=True)

        def clamp(v):
            return min(cap, max(0, v))

        relevance = clamp(selected / best)
        quality = clamp(sum(ratios) / len(ratios))
        overall = clamp(
            number(policy.get('Build relevance share')) * relevance
            + number(policy.get('Roll quality share')) * quality
        )
        verdict = (
            'Keep'
            if overall >= number(policy.get('Keep threshold'))
            else 'Review'
            if overall >= number(policy.get('Review threshold'))
            else 'Recycle'
        )
        return {
            **out,
            'Status': 'AVAILABLE',
            'Relevance': text(relevance),
            'Quality': text(quality),
            'Overall': text(overall),
            'Recommendation': verdict,
            'Model': 'HEURISTIC',
        }
    except (ValueUnavailable, KeyError) as exc:
        return {**out, 'Diagnostic': str(exc)}
