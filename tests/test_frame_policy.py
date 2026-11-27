from nte_gear_optimizer_app.frame_policy import frame_limit
import pytest


@pytest.mark.parametrize(
    'active,native,expected',
    [
        (60, 120, 120),
        (60, None, 60),
        (119.99999, 119.99999, 120),
        (None, None, None),
        (float('nan'), None, None),
        (0, 0, None),
    ],
)
def test_native_frequency_is_not_silently_replaced_by60(active, native, expected):
    assert frame_limit({'active_hz': active, 'native_max_hz': native}) == expected
