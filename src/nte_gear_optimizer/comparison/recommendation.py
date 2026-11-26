"""Compose independent output blocks; §13 forbids unrelated global gates.

Inputs are canonical values and released records, not persisted calculations.
The I/O layer is deliberately outside this pure core.
"""

from dataclasses import replace
from .decision import invalidate_decision
from ..models.profile_state import effective_profile
from ..numbers import number, text, isolated, ValueUnavailable
from ..guide.reference import reference, rank_verdict, quarantine_optional_targets
from ..rules.opb10 import evaluate as round_ratio
from .robust_branches import Branch, evaluate_profile, evaluate_branches, MISSING


def known_deltas(values):
    deltas = {}
    for key in sorted(values):
        if not key.startswith('Before'):
            continue
        after = 'After' + key[6:]
        if after not in values:
            continue
        try:
            deltas[key[6:]] = text(
                number(values[after], after) - number(values[key], key)
            )
        except ValueUnavailable:
            pass
    return deltas


@isolated
def apply_condition(result, conditional_factors):
    out = dict(result)
    if out.get('OutputStatus') != 'READY':
        return out
    lo = out.get('RatioMin') or out.get('RawRatio')
    hi = out.get('RatioMax') or out.get('RawRatio')
    if lo is None or hi is None:
        return invalidate_decision(
            out, OutputStatus='INDETERMINATE_CONDITIONAL_COMPONENT'
        )
    candidates = []
    try:
        for condition in conditional_factors:
            b = number(condition.get('BeforeFactor'), 'BeforeFactor', nonnegative=True)
            a = number(condition.get('AfterFactor'), 'AfterFactor', nonnegative=True)
            if b <= 0:
                raise ValueUnavailable('BeforeFactor')
            candidates.extend(number(r) * a / b for r in (lo, hi))
        lower, upper = min(candidates), max(candidates)
        verdicts = {round_ratio(text(r)).verdict for r in candidates}
        out.update(
            BaseProxyRatio=out.get('RawRatio'),
            RatioMin=text(lower),
            RatioMax=text(upper),
            RawRatio=text(lower) if lower == upper else None,
            VerdictRatio=round_ratio(text(lower)).rounded if lower == upper else None,
        )
        if len(verdicts) != 1:
            out = invalidate_decision(
                out, OutputStatus='INDETERMINATE_CONDITIONAL_COMPONENT'
            )
        else:
            out['Verdict'] = next(iter(verdicts))
    except ValueUnavailable as exc:
        out = invalidate_decision(
            out,
            BaseProxyRatio=out.get('RawRatio'),
            OutputStatus='INDETERMINATE_CONDITIONAL_COMPONENT',
            Diagnostics=[str(exc)],
        )
    return out


@isolated
def compare(
    values,
    release_profile,
    *,
    branches=(),
    expected_branch_ids=None,
    targets=(),
    conditional_factors=(),
    optional_targets=(),
    ark_issue=None,
    layout_issue=None,
    ruleset='CURRENT',
):
    selected = values.get('SelectedBranchID')
    override_id = values.get('ProfileOverrideBranchID')
    profile = effective_profile(
        release_profile, values, branch_id=selected, override_branch_id=override_id
    )
    refs = [reference(row) for row in targets]
    out = {
        'ItemDeltas': 'PRESERVED',
        'Deltas': known_deltas(values),
        'GuideReferenceBlock': refs,
        'DroveRecommendation': False,
        'EffectiveSources': dict(profile.sources),
        'EffectiveSource': profile.sources['CritEligible'],
        'CritEligible': profile.values['CritEligible'],
        'ProfileDiagnostics': list(profile.diagnostics),
    }
    if ark_issue is not None:
        out['ArkDependentOutputs'] = 'UNKNOWN'
    if refs:
        for key in (
            'Trend',
            'BeforeAligned',
            'AfterAligned',
            'RawDelta',
            'ReferenceUnavailableReason',
        ):
            out[key] = refs[0].get(key)
    elif 'ReferenceBasis' in values and values['ReferenceBasis'] is None:
        out['ReferenceUnavailableReason'] = 'BASIS_UNVERIFIED'
    _, quarantined = quarantine_optional_targets(optional_targets)
    if quarantined:
        # This checks optional relation scope, not a file-import transaction.
        out.update(
            CollidingUserTargets='QUARANTINED',
            GuideFallback=True,
            ValidBuildCommit=True,
            QuarantinedTargetCount=len(quarantined),
        )
    if profile.values['ScalingStat'] in ('SONSTIGE', 'BASIS_ANG') and not branches:
        result = {'RawRatio': None, **rank_verdict(refs)}
    elif branches:
        profile_id = release_profile.get('BuildProfileID')
        relevant = [b for b in branches if selected is None or b.branch_id == selected]
        if profile_id is not None and any(
            b.profile.get('BuildProfileID') != profile_id for b in relevant
        ):
            return invalidate_decision(
                out,
                clear_nested=True,
                OutputStatus=MISSING,
                ProductDerivationStatus='FAIL',
                Diagnostics=['BuildProfileID: Zweig gehört nicht zum Profil'],
            )
        effective = []
        for b in branches:
            p = effective_profile(
                {**release_profile, **b.profile},
                values,
                branch_id=b.branch_id,
                override_branch_id=override_id,
            )
            effective.append(replace(b, profile=p.values))
        result = evaluate_branches(
            effective, values, selected_id=selected, expected_ids=expected_branch_ids
        )
        if selected is not None:
            p = next((p for p in effective if p.branch_id == selected), None)
            if p:
                ep = effective_profile(
                    {
                        **release_profile,
                        **next(b.profile for b in branches if b.branch_id == selected),
                    },
                    values,
                    branch_id=selected,
                    override_branch_id=override_id,
                )
                out.update(
                    CritEligible=ep.values['CritEligible'],
                    EffectiveSource=ep.sources['CritEligible'],
                    EffectiveSources=dict(ep.sources),
                )
    else:
        result = evaluate_profile(values, profile.values)
    out.update(result)
    if conditional_factors:
        if out.get('BranchEvaluations'):
            evaluated = [
                apply_condition(r, conditional_factors)
                for r in out['BranchEvaluations']
            ]
            out['BranchEvaluations'] = evaluated
            if selected is not None:
                out.update(evaluated[0])
            elif any(
                r.get('OutputStatus') == 'INDETERMINATE_CONDITIONAL_COMPONENT'
                for r in evaluated
            ):
                out = invalidate_decision(
                    out,
                    clear_nested=True,
                    OutputStatus='INDETERMINATE_CONDITIONAL_COMPONENT',
                )
        else:
            out = apply_condition(out, conditional_factors)
    if layout_issue is not None:
        out = invalidate_decision(
            out,
            clear_nested=True,
            BuildOutcome=layout_issue.outcome,
            ErrorCode=layout_issue.code,
            OutputStatus=MISSING,
            Diagnostics=[*out.get('Diagnostics', []), layout_issue.help],
        )
    if ruleset == 'UNKNOWN':
        out = invalidate_decision(out, clear_nested=True, OutputStatus=MISSING)
    elif ruleset == 'SUPERSEDED':
        out.update(
            Notice='RULESET_SUPERSEDED_UNVERIFIED',
            RecommendationQualification='VORLÄUFIG',
        )
    return out
