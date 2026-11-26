"""Invalidate judgment outputs while retaining independent measurements/evidence."""

DECISION_FIELDS = (
    'Verdict', 'RawRatio', 'VerdictRatio', 'RatioMin', 'RatioMax',
    'Recommendation', 'RecommendationQualification', 'DecisionRank', 'BranchStatus',
)

def invalidate_decision(result, *, clear_nested=False, **metadata):
    out = dict(result)
    out.update({field: None for field in DECISION_FIELDS})
    out['DroveRecommendation'] = False
    if 'GuideReferenceBlock' in out:
        out['GuideReferenceBlock'] = [dict(row, DroveRecommendation=False) for row in out['GuideReferenceBlock']]
    if clear_nested and out.get('BranchEvaluations'):
        out['BranchEvaluations'] = [invalidate_decision(row, clear_nested=True, OutputStatus=metadata.get('OutputStatus', row.get('OutputStatus'))) for row in out['BranchEvaluations']]
    out.update(metadata)
    return out
