"""Shared, packaged design contract; independent of Kivy and calculation code."""

import json
from importlib.resources import files

TOKENS = json.loads(
    files('nte_gear_optimizer_app')
    .joinpath('assets/design_tokens.json')
    .read_text(encoding='utf-8')
)


def rgba(name):
    value = TOKENS['colors'][name].lstrip('#')
    return tuple(int(value[i : i + 2], 16) / 255 for i in (0, 2, 4)) + (1,)


def contrast(foreground, background):
    def luminance(name):
        channels = rgba(name)[:3]
        linear = [
            v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
            for v in channels
        ]
        return sum(v * w for v, w in zip(linear, (0.2126, 0.7152, 0.0722)))

    a, b = sorted((luminance(foreground), luminance(background)))
    return (b + 0.05) / (a + 0.05)


def result_sections(summary, changed, hints):
    """Partition existing display text without losing any explanations."""
    leading, tail = summary.split('\n\n' + changed, 1)
    changed_text = changed + tail
    before_hints, hint_text = changed_text.split('\n\n' + hints + '\n', 1)
    if '\n\nGuide\n' in before_hints:
        changes, guide = before_hints.split('\n\nGuide\n', 1)
    else:
        changes, guide = before_hints, ''
    return leading, changes, guide, hint_text
