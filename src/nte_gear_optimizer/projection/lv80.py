"""OPB-18/19: display-only projection, never fed back into current panels."""

from ..numbers import number, text, isolated, ValueUnavailable


@isolated
def project(values):
    result = {
        'Projection': None,
        'ProjectedLv80': None,
        'ProjectedLv80Exact': None,
        'ProjectedLv80Minimum': None,
    }
    basis = values.get('WhiteBasis')
    if basis != 'IN_GAME_WHITE_WITH_PROGRESS':
        return {
            **result,
            'ProjectionReason': 'RAW_LEVEL_STAT_NOT_WHITE_BASIS'
            if basis == 'RAW_LEVEL_STAT'
            else 'BASIS_DEFINITION_OPEN',
        }
    try:
        actual = number(values.get('ActualTotal'), 'ActualTotal', nonnegative=True)
        white = number(values.get('WhiteCurrent'), 'WhiteCurrent', nonnegative=True)
        white80 = number(values.get('White80'), 'White80', nonnegative=True)
        if white80 < white:
            raise ValueUnavailable('White80', True)
        delta = white80 - white
        minimum = actual + delta
        result.update(ProjectedLv80Minimum=text(minimum), ProjectionKind='MINIMUM')
        if values.get('EquipmentPercent') is not None:
            percent = number(
                values['EquipmentPercent'], 'EquipmentPercent', nonnegative=True
            )
            exact = actual + delta * (1 + percent / 100)
            result.update(
                Projection=text(exact),
                ProjectedLv80=text(exact),
                ProjectedLv80Exact=text(exact),
                ProjectionKind='EXACT',
            )
        return result
    except ValueUnavailable as exc:
        return {**result, 'ProjectionReason': str(exc)}
