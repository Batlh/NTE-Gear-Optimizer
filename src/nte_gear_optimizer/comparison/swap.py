"""Apply Y-X to current totals that already contain X; never count X twice."""

from ..numbers import number, text, isolated, ValueUnavailable


@isolated
def compile_swap(current, item_x, item_y, fields, *, white_panel_base=None):
    values, deltas, diagnostics = {}, {}, []
    for field in fields:
        values['Before' + field] = current.get(field)
        values['After' + field] = None
        try:
            x = number(item_x.get(field), 'Teil X: ' + field)
            y = number(item_y.get(field), 'Teil Y: ' + field)
            delta = y - x
            deltas[field] = text(delta)
            before = number(current.get(field), 'Aktuell: ' + field)
            values['After' + field] = text(before + delta)
        except ValueUnavailable as exc:
            diagnostics.append(str(exc))
    if 'ScaleDirect' in fields:
        try:
            x = number(item_x.get('ScalingPercentPP'), 'Teil X: ScalingPercentPP')
            y = number(item_y.get('ScalingPercentPP'), 'Teil Y: ScalingPercentPP')
            delta = y - x
            deltas['ScalingPercentPP'] = text(delta)
            if delta != 0:
                white = number(white_panel_base, 'WhitePanelBase', nonnegative=True)
                if values.get('AfterScaleDirect') is not None:
                    values['AfterScaleDirect'] = text(
                        number(values['AfterScaleDirect']) + white * delta / 100
                    )
        except ValueUnavailable as exc:
            values['AfterScaleDirect'] = None
            diagnostics.append(str(exc))
    return {'Values': values, 'PartDeltas': deltas, 'Diagnostics': diagnostics}
