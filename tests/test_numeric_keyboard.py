"""Number flags and focus handoffs must not alter the accepted parser."""

from pathlib import Path
import runpy
from types import SimpleNamespace

import pytest

from nte_gear_optimizer_app.numeric_keyboard import NumericKeyboard, flags_for
from nte_gear_optimizer_app.viewmodel import (
    normalize,
    numeric_hint,
    ark_level_hint,
    InputFormatError,
)

ROOT = Path(__file__).resolve().parents[1]


def test_decimal_signed_flags_and_integer_level_are_explicit():
    decimal = SimpleNamespace(_nte_integer_only=False)
    level = SimpleNamespace(_nte_integer_only=True)
    assert flags_for(decimal) == 0x3002 and flags_for(level) == 2
    applied = []
    bridge = NumericKeyboard(applied.append, lambda *a, **k: None)
    bridge.configure(decimal, True)
    for _ in range(10):
        bridge.configure(decimal, False)
    bridge.configure(level, False)
    bridge.configure(decimal, False)
    bridge.configure(decimal, True)
    assert applied == [12290, 2, 12290, 12290]


def test_actual_managed_keyboard_handoff_preserves_native_editor():
    fixtures = runpy.run_path(str(ROOT / 'tests/test_keyboard_session.py'))
    session, window, clock, a, b, c, journal = fixtures['setup']()
    applied = []
    bridge = NumericKeyboard(applied.append, lambda *a, **k: None)
    session.configure_widget = bridge.configure
    for w in [a, b, c]:
        w.input_type = 'number'
    c._nte_integer_only = True
    for w in [a, b, a, c, b]:
        fixtures['focus'](session, w)
        clock.flush()
    assert window.requests == 1 and window.releases == 0
    assert applied == [12290, 2, 12290]
    session.close()
    fixtures['focus'](session, a)
    assert window.requests == 2 and applied == [12290, 2, 12290, 12290]


@pytest.mark.parametrize('text', ['2.560', '12.345', '1.234.567', '1.5'])
def test_keypad_never_converts_dot_to_a_different_value(text):
    with pytest.raises(InputFormatError):
        normalize(text)
    assert numeric_hint(text)


@pytest.mark.parametrize(
    'text,expected', [('1,5', '1.5'), ('2560', '2560'), ('-1,5', '-1.5'), ('0', '0')]
)
def test_comma_signed_and_integer_values_unchanged(text, expected):
    assert normalize(text) == expected


@pytest.mark.parametrize('text', ['80,8', '80.8', '80 8', '80ü8', '😀'])
def test_integer_keypad_does_not_suppress_validation_of_invalid_paste(text):
    assert ark_level_hint(text)
    assert not ark_level_hint('80')
