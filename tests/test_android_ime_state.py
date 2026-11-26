"""Regression: actual API33 Gboard retains mIsInputViewShown after hiding."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    'android_ime_state', Path(__file__).parents[1] / 'tools/android_ime_state.py'
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
read_ime_state = module.read_ime_state


@pytest.mark.parametrize(
    ('current', 'window', 'expected'),
    [('false', 'false', False), ('true', 'true', True)],
)
def test_current_window_not_gboard_internal_view(current, window, expected):
    dump = f'mInputShown={current}\n  mStartInputHistory:\nold mInputShown=true\nInput method service state for LatinIME:\nmWindowVisible={window} mIsInputViewShown=true'
    assert read_ime_state(dump)['shown'] is expected


@pytest.mark.parametrize(
    'dump',
    [
        'mIsInputViewShown=true',
        'mInputShown=false',
        'mInputShown=false mInputShown=false\nInput method service state for LatinIME:\nmWindowVisible=false',
        'mInputShown=false\nInput method service state for LatinIME:\nmWindowVisible=true',
        'mInputShown=true\nInput method service state for LatinIME:\nmWindowVisible=false',
        'mInputShown=false\nInput method service state for LatinIME:\nmWindowVisible=false mWindowVisible=false',
    ],
)
def test_missing_ambiguous_or_transitional_state_is_not_pass(dump):
    with pytest.raises(ValueError):
        read_ime_state(dump)
