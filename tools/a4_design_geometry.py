"""CI graphics unit check in Kivy's normal Window event/render loop."""

import os, sys, json, traceback
from pathlib import Path

assert os.environ.get('GITHUB_ACTIONS') == 'true'
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.widget import Widget
from kivy.metrics import dp
from nte_gear_optimizer_app.design_widgets import DesignButton, DesignTextInput

OUT = Path('build/a4_geometry')
OUT.mkdir(parents=True, exist_ok=False)


class GeometryApp(App):
    failure = None

    def build(self):
        root = Widget()
        self.samples = (
            DesignButton(size_hint=(None, None)),
            DesignTextInput(size_hint=(None, None)),
        )
        for w in self.samples:
            root.add_widget(w)
        return root

    def on_start(self):
        self.actions = self.scenario()
        Clock.schedule_once(self.advance, 0.2)

    def advance(self, dt):
        try:
            delay = next(self.actions)
        except StopIteration:
            self.stop()
            return
        except Exception:
            self.failure = traceback.format_exc()
            (OUT / 'failure.txt').write_text(
                self.failure, encoding='utf-8', newline='\n'
            )
            self.stop()
            return
        Clock.schedule_once(self.advance, delay)

    def scenario(self):
        rows = []
        for widget in self.samples:
            widget.size = (dp(260), dp(52))
            yield 0.2
            geometry = (
                widget.edge.source,
                tuple(widget.edge.border),
                tuple(widget.edge.display_border),
                widget.edge.texture.id,
            )
            fill_source = widget.fill.source
            for x, y in ((10, 20), (37, 91), (401, -533), (0, 0)):
                widget.pos = (x, y)
                yield 0.1
                assert (
                    widget.edge.source,
                    tuple(widget.edge.border),
                    tuple(widget.edge.display_border),
                    widget.edge.texture.id,
                ) == geometry
                assert tuple(widget.fill.pos) == tuple(widget.edge.pos) == (x, y)
                assert widget.fill.source == fill_source
                assert (
                    widget.decoration_position.x == x
                    and widget.decoration_position.y == y
                )
            widget.width += dp(20)
            yield 0.1
            assert (
                widget.edge.source,
                tuple(widget.edge.border),
                tuple(widget.edge.display_border),
                widget.edge.texture.id,
            ) == geometry
            assert tuple(widget.edge.size) == tuple(widget.size)
            assert tuple(widget.fill.size) == tuple(widget.size)
            rows.append(
                {
                    'widget': type(widget).__name__,
                    'position_changes': 4,
                    'shared_texture_and_slices': True,
                    'resize_updates': True,
                }
            )
        (OUT / 'result.json').write_text(
            json.dumps(
                {
                    'status': 'PASS',
                    'scope': 'CI graphics unit check in normal Window render loop; not native touch evidence',
                    'rows': rows,
                },
                indent=2,
            )
            + '\n',
            encoding='utf-8',
            newline='\n',
        )
        print('Nine-slice texture reuse and native geometry checks PASS')


app = GeometryApp()
app.run()
if app.failure:
    raise SystemExit(app.failure)
assert (OUT / 'result.json').exists()
