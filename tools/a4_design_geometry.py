"""CI-only graphics unit check; not a native touch/performance claim."""

import os, sys, json
from pathlib import Path

assert os.environ.get('GITHUB_ACTIONS') == 'true'
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from nte_gear_optimizer_app.design_widgets import DesignButton, DesignTextInput
from kivy.metrics import dp

rows = []
for widget in (DesignButton(), DesignTextInput()):
    widget.size = (dp(260), dp(52))
    geometry = tuple(widget.edge.rounded_rectangle)
    fill_pos = tuple(widget.fill.pos)
    for x, y in ((10, 20), (37, 91), (401, -533), (0, 0)):
        widget.pos = (x, y)
        assert tuple(widget.edge.rounded_rectangle) == geometry
        assert tuple(widget.fill.pos) == fill_pos == (0, 0)
        assert widget.decoration_position.x == x and widget.decoration_position.y == y
    widget.width += dp(20)
    assert tuple(widget.edge.rounded_rectangle) != geometry
    assert tuple(widget.fill.size) == tuple(widget.size)
    rows.append(
        {
            'widget': type(widget).__name__,
            'position_changes': 4,
            'cached_outline': True,
            'resize_updates': True,
        }
    )
out = Path('build/a4_geometry')
out.mkdir(parents=True, exist_ok=False)
(out / 'result.json').write_text(
    json.dumps(
        {
            'status': 'PASS',
            'scope': 'CI graphics unit test, not native touch evidence',
            'rows': rows,
        },
        indent=2,
    )
    + '\n',
    encoding='utf-8',
    newline='\n',
)
print('Decoration translation/resize graphics unit checks PASS')
