"""Use Kivy's own single-background control path with token-colored nine-slices."""

from importlib.resources import files
from kivy.graphics import Color, Line, RoundedRectangle, BorderImage
from kivy.metrics import dp, sp
from kivy.properties import StringProperty, NumericProperty
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from .reconcile_layout import ReconcileLayout
from .design_tokens import rgba


def patch_source(style):
    return str(files('nte_gear_optimizer_app').joinpath(f'assets/ui_masks/{style}.png'))


def native_patch(canvas):
    patches = [
        instruction
        for instruction in canvas.children
        if isinstance(instruction, BorderImage)
    ]
    assert len(patches) == 1, 'Pinned Kivy2.3.2 control background changed'
    return patches[0]


class DesignButton(Button):
    role = StringProperty('outline')

    def __init__(self, **kwargs):
        kwargs.setdefault('background_color', (1, 1, 1, 1))
        kwargs.setdefault('font_size', sp(16))
        super().__init__(**kwargs)
        # Exactly the original Button BorderImage: no extra translucent
        # full-area layers, tessellated outlines or per-control matrix stack.
        self.fill = native_patch(self.canvas)
        self.edge = self.fill
        self.bind(state=self.style, role=self.style, disabled=self.style)
        self.style()

    def style(self, *_):
        role = self.role
        primary = role == 'primary'
        pill = role == 'pill'
        self.background_normal = patch_source(role + '_normal')
        self.background_down = patch_source(role + '_down')
        self.background_disabled_normal = self.background_normal
        self.background_disabled_down = self.background_down
        radius = 24 if pill else 12
        self.border = [(radius + 1) * 4] * 4
        self.fill.display_border = [dp(radius + 1)] * 4
        self.color = rgba(
            'accent_ink' if primary else ('accent_text' if pill else 'text')
        )
        self.disabled_color = rgba('muted')


class DesignTextInput(TextInput):
    def __init__(self, **kwargs):
        kwargs.update(
            background_normal=patch_source('input_normal'),
            background_active=patch_source('input_focus'),
            background_color=(1, 1, 1, 1),
            foreground_color=rgba('text'),
            cursor_color=rgba('accent_text'),
            selection_color=(*rgba('accent')[:3], 0.3),
            padding=[dp(12), dp(12)],
            border=[44] * 4,
        )
        super().__init__(**kwargs)
        # Preserve Kivy's cursor, selection and foreground instructions.
        self.fill = native_patch(self.canvas.before)
        self.edge = self.fill
        self.fill.display_border = [dp(11)] * 4


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
