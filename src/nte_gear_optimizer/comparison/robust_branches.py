"""OPB-03/09: enumerate unknown scenarios and released branches; never average."""

from itertools import product
from .decision import invalidate_decision
from dataclasses import dataclass, field
from typing import Mapping
from ..numbers import number, text, isolated, ValueUnavailable
from ..rules.opb10 import evaluate as round_ratio
from .factors import scenarios, domain, REACTIONS

MISSING = 'INDETERMINATE_MISSING_DEPENDENCY'


@dataclass(frozen=True)
class Branch:
    branch_id: str
    profile: Mapping
    values: Mapping = field(default_factory=dict)
    offset_status: str = 'ZERO'
    offset_minimum: str | None = None
    coefficient: str | None = None
    targets: tuple = ()


@isolated
def affine_status(rows, offset_status, minimum, coefficient, verdict):
    if offset_status == 'UNKNOWN':
        return 'FIXED_OFFSET_STATUS_UNKNOWN', None
    if offset_status == 'ZERO':
        return 'AFFINE_PROXY_ALLOWED', None
    if offset_status != 'POSITIVE' or not rows:
        return 'FIXED_OFFSET_THRESHOLD_DATA_UNAVAILABLE', None
    if all(s.before_scale == s.after_scale for s in rows):
        return 'AFFINE_PROXY_ALLOWED', None
    if any(s.factor_changed for s in rows):
        return 'AFFINE_OFFSET_NOT_MODELLED', None
    if verdict == 'EQUAL':
        return 'AFFINE_PROXY_ALLOWED', None
    try:
        b = number(minimum, 'FixedOffsetMinimum', nonnegative=True)
        a = number(coefficient, 'ScalingCoefficientLevel1', nonnegative=True)
        if a <= 0 or b <= 0:
            raise ValueUnavailable('FixedOffsetMinimum')
        ratios = [(b + a * s.after_scale) / (b + a * s.before_scale) for s in rows]
        if all(round_ratio(text(r)).verdict == verdict for r in ratios):
            return 'AFFINE_THRESHOLD_CROSSED', text(min(ratios))
        return 'FIXED_OFFSET_NEAR_THRESHOLD', text(min(ratios))
    except ValueUnavailable, ZeroDivisionError:
        return 'FIXED_OFFSET_THRESHOLD_DATA_UNAVAILABLE', None


@isolated
def evaluate_profile(
    values, profile, *, offset_status='ZERO', offset_minimum=None, coefficient=None
):
    result = {
        'RawRatio': None,
        'RatioMin': None,
        'RatioMax': None,
        'Verdict': None,
        'VerdictRatio': None,
        'OutputStatus': MISSING,
        'Diagnostics': [],
    }
    rows = []
    missing = []
    invalid = False
    try:
        domains = (
            (
                domain(profile, 'CritEligible', ('FALSE', 'TRUE')),
                domain(profile, 'BreakEligible', ('FALSE', 'TRUE')),
                domain(profile, 'CycleType', REACTIONS),
            )
            if profile.get('ProfileType') == 'DAMAGE'
            else (('FALSE',), ('FALSE',), ('NONE',))
        )
        for crit, brk, reaction in product(*domains):
            p = {
                **profile,
                'CritEligible': crit,
                'BreakEligible': brk,
                'CycleType': reaction,
            }
            try:
                rows.extend(scenarios(values, p))
            except ValueUnavailable as exc:
                missing.append(str(exc))
                invalid |= exc.invalid
    except ValueUnavailable as exc:
        missing.append(str(exc))
        invalid |= exc.invalid
    result['Diagnostics'] = missing
    if rows:
        lo, hi = min(s.ratio for s in rows), max(s.ratio for s in rows)
        result.update(RatioMin=text(lo), RatioMax=text(hi))
        verdicts = {round_ratio(text(s.ratio)).verdict for s in rows}
        if not missing and len(verdicts) == 1:
            result.update(OutputStatus='READY', Verdict=next(iter(verdicts)))
            if lo == hi:
                result.update(
                    RawRatio=text(lo), VerdictRatio=round_ratio(text(lo)).rounded
                )
    result['ScenarioCount'] = len(rows)
    result['Recommendation'] = (
        'Ungültige Eingaben – Wertebereich prüfen' if invalid else result['Verdict']
    )
    status, threshold = affine_status(
        rows, offset_status, offset_minimum, coefficient, result['Verdict']
    )
    result.update(AffineStatus=status, AffineThresholdRatio=threshold)
    if result['OutputStatus'] == 'READY' and status in (
        'FIXED_OFFSET_NEAR_THRESHOLD',
        'AFFINE_OFFSET_NOT_MODELLED',
        'FIXED_OFFSET_THRESHOLD_DATA_UNAVAILABLE',
    ):
        result = invalidate_decision(
            result,
            preserve_proxy=True,
            BaseProxyRatio=result.get('RawRatio'),
            OutputStatus='NICHT_ENTSCHEIDBAR',
        )
    if status == 'FIXED_OFFSET_STATUS_UNKNOWN':
        result['Notice'] = status
    return result


def evaluate_branches(branches, base_values, *, selected_id=None, expected_ids=None):
    ids = [b.branch_id for b in branches]
    relevant = (
        [b for b in branches if b.branch_id == selected_id]
        if selected_id is not None
        else list(branches)
    )
    if (
        not relevant
        or len({b.branch_id for b in relevant}) != len(relevant)
        or (
            selected_id is None
            and expected_ids is not None
            and (
                set(ids) != set(expected_ids)
                or len(expected_ids) != len(set(expected_ids))
            )
        )
    ):
        return {
            'OutputStatus': MISSING,
            'Verdict': None,
            'RawRatio': None,
            'BranchStatus': MISSING,
            'BranchEvaluations': [],
        }
    evaluated = []
    for b in sorted(relevant, key=lambda b: b.branch_id):
        if b.profile.get('ScalingStat') in ('BASIS_ANG', 'SONSTIGE'):
            from ..guide.reference import reference, rank_verdict

            refs = [reference(row) for row in b.targets]
            r = {'RawRatio': None, **rank_verdict(refs), 'GuideReferenceBlock': refs}
        else:
            r = evaluate_profile(
                {**base_values, **b.values},
                b.profile,
                offset_status=b.offset_status,
                offset_minimum=b.offset_minimum,
                coefficient=b.coefficient,
            )
        evaluated.append({'BranchID': b.branch_id, **r})
    if selected_id is not None:
        return {**evaluated[0], 'BranchEvaluations': evaluated}
    base = {
        'RawRatio': None,
        'VerdictRatio': None,
        'Verdict': None,
        'BranchEvaluations': evaluated,
    }
    if any(r['OutputStatus'] == MISSING for r in evaluated):
        return {**base, 'OutputStatus': MISSING, 'BranchStatus': MISSING}
    verdicts = {r['Verdict'] for r in evaluated}
    if (
        any(r['OutputStatus'] != 'READY' for r in evaluated)
        or len(verdicts) != 1
        or None in verdicts
    ):
        return {
            **base,
            'OutputStatus': 'NICHT_ENTSCHEIDBAR',
            'BranchStatus': 'BRANCHES_DISAGREE',
        }
    return {
        **base,
        'OutputStatus': 'READY',
        'BranchStatus': 'CONSENSUS',
        'Verdict': next(iter(verdicts)),
    }
