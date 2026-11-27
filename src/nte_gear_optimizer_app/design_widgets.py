"""Constant-size nine-slice decorations; no overlay widgets intercept input."""

from importlib.resources import files
from kivy.graphics import Color, Line, RoundedRectangle, InstructionGroup, BorderImage
from kivy.metrics import dp, sp
from kivy.properties import StringProperty, NumericProperty
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from .reconcile_layout import ReconcileLayout
from .design_tokens import rgba, TOKENS


def set_round_patch(patch, radius, kind):
    # Source has4pixels/dp and a1dp stretchable center. Display borders use
    # actual density, while texture slice borders remain source pixels.
    patch.source = str(
        files('nte_gear_optimizer_app').joinpath(
            f'assets/ui_masks/round_{kind}_r{radius}.png'
        )
    )
    patch.border = [(radius + 1) * 4] * 4
    patch.display_border = [dp(radius + 1)] * 4


class DesignButton(Button):
    role = StringProperty('outline')

    def __init__(self, **kwargs):
        kwargs.setdefault('background_normal', '')
        kwargs.setdefault('background_down', '')
        kwargs.setdefault('background_color', (0, 0, 0, 0))
        kwargs.setdefault('font_size', sp(16))
        super().__init__(**kwargs)
        with self.canvas.before:
            self.fill_color = Color(*rgba('surface'))
            self.fill = BorderImage(
                pos=self.pos, size=self.size, auto_scale='both_lower'
            )
            self.line_color = Color(*rgba('border'))
            self.edge = BorderImage(
                pos=self.pos, size=self.size, auto_scale='both_lower'
            )
        self.bind(
            pos=self.geometry,
            size=self.geometry,
            state=self.style,
            role=self.style,
            disabled=self.style,
        )
        self.style()

    def geometry(self, *_):
        self.fill.pos = self.edge.pos = self.pos
        self.fill.size = self.edge.size = self.size

    def style(self, *_):
        primary = self.role == 'primary'
        pill = self.role == 'pill'
        text = self.role == 'text'
        fill = (
            ('accent_text' if self.state == 'down' else 'accent')
            if primary
            else ('surface2' if self.state == 'down' else 'surface')
        )
        self.fill_color.rgba = (
            rgba(fill) if not text or self.state == 'down' else (0, 0, 0, 0)
        )
        self.line_color.rgba = (
            rgba('accent' if pill or self.state == 'down' else 'border')
            if not text and not primary
            else (0, 0, 0, 0)
        )
        self.color = rgba(
            'accent_ink' if primary else ('accent_text' if pill else 'text')
        )
        self.disabled_color = rgba('muted')
        radius = 24 if pill else TOKENS['radii_dp']['button']
        if radius != getattr(self, '_patch_radius', None):
            self._patch_radius = radius
            set_round_patch(self.fill, radius, 'fill')
            set_round_patch(self.edge, radius, 'edge')


class DesignTextInput(TextInput):
    def __init__(self, **kwargs):
        kwargs.update(
            background_normal='',
            background_active='',
            background_color=(0, 0, 0, 0),
            foreground_color=rgba('text'),
            cursor_color=rgba('accent_text'),
            selection_color=(*rgba('accent')[:3], 0.3),
            padding=[dp(12), dp(12)],
        )
        super().__init__(**kwargs)
        # Keep decorations before Kivy's cursor/foreground; no canvas overlay.
        decoration = InstructionGroup()
        decoration.add(Color(*rgba('background')))
        self.fill = BorderImage(pos=self.pos, size=self.size, auto_scale='both_lower')
        decoration.add(self.fill)
        self.line_color = Color(*rgba('border'))
        decoration.add(self.line_color)
        self.edge = BorderImage(pos=self.pos, size=self.size, auto_scale='both_lower')
        decoration.add(self.edge)
        self.canvas.before.insert(0, decoration)
        set_round_patch(self.fill, 10, 'fill')
        set_round_patch(self.edge, 10, 'edge')
        self.bind(pos=self.geometry, size=self.geometry, focus=self.style)
        self.style()

    def style(self, *_):
        self.line_color.rgba = rgba('accent' if self.focus else 'border')

    def geometry(self, *_):
        self.fill.pos = self.edge.pos = self.pos
        self.fill.size = self.edge.size = self.size


class ResultCard(ReconcileLayout):
    def __init__(self, **kwargs):
        super().__init__(
            orientation='vertical',
            size_hint_y=None,
            padding=dp(16),
            spacing=dp(8),
            **kwargs,
        )
        self.bind(minimum_height=self.setter('height'))
        with self.canvas.before:
            Color(*rgba('surface'))
            self.fill = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(16)])
        self.bind(pos=self.geometry, size=self.geometry)

    def geometry(self, *_):
        self.fill.pos = self.pos
        self.fill.size = self.size


class VerdictMark(Widget):
    verdict = StringProperty('')

    def __init__(self, **kwargs):
        super().__init__(size_hint=(None, None), size=(dp(40), dp(40)), **kwargs)
        with self.canvas:
            self.tint = Color(*rgba('equal'))
            self.stem = Line(width=dp(2))
            self.head = Line(width=dp(2))
        self.bind(pos=self.paint, size=self.paint, verdict=self.paint)
        self.paint()

    def paint(self, *_):
        x, y = self.center
        h = dp(10)
        self.tint.rgba = rgba(
            'accent_text'
            if self.verdict == 'BETTER'
            else ('warning_text' if self.verdict == 'WORSE' else 'equal')
        )
        if self.verdict in ('BETTER', 'WORSE'):
            direction = 1 if self.verdict == 'BETTER' else -1
            self.stem.points = [x, y - direction * h, x, y + direction * h]
            self.head.points = [x - h, y, x, y + direction * h, x + h, y]
        else:
            self.stem.points = [x - h, y + dp(4), x + h, y + dp(4)]
            self.head.points = (
                [x - h, y - dp(4), x + h, y - dp(4)] if self.verdict == 'EQUAL' else []
            )


class StepSegments(Widget):
    step = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(size_hint_y=None, height=dp(8), **kwargs)
        self.segments = []
        with self.canvas:
            for _ in range(4):
                self.segments.append(
                    (Color(*rgba('border')), RoundedRectangle(radius=[dp(4)]))
                )
        self.bind(pos=self.paint, size=self.paint, step=self.paint)
        self.paint()

    def paint(self, *_):
        width = max(0, (self.width - dp(8) * 3) / 4)
        for i, (color, shape) in enumerate(self.segments):
            color.rgba = rgba('accent' if i <= self.step else 'border')
            shape.pos = (self.x + i * (width + dp(8)), self.y)
            shape.size = (width, self.height)
