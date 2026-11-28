"""Actual layout observations, no input or geometry mutation."""


def verify_rectangles(rects):
    def center(r):
        return r[1] + r[3] / 2

    header, kiwi, titles, title, subtitle = (
        rects[n] for n in ('header', 'kiwi', 'titles', 'title', 'subtitle')
    )
    assert abs(center(header) - center(kiwi)) < 1, rects
    assert abs(center(kiwi) - center(titles)) < 1, rects
    assert kiwi[0] + kiwi[2] <= titles[0], rects
    assert abs(title[0] - subtitle[0]) < 1, rects
    assert title[1] >= subtitle[1] + subtitle[3] - 0.1, rects
    return {'header_geometry': 'PASS', 'rectangles': rects}


def verify_header(app):
    return verify_rectangles(
        {n: [*w.pos, *w.size] for n, w in app.header_widgets.items()}
    )
