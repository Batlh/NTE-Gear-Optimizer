from math import nan, inf
import pytest
from nte_gear_optimizer_app.touch_intent import TouchIntent


@pytest.mark.parametrize('duration', [0.01, 0.3, 0.4, 1.0, 10.0])
@pytest.mark.parametrize('distance', [0, 3, 6, 8])
def test_tap_with_jitter_and_hold_independent_of_duration(duration, distance):
    intent = TouchIntent(20, 30, 8, started=0)
    for i in range(20):
        assert intent.move(20 + (distance if i % 2 else 0), 30) == 'TAP'
    result = intent.finish(20 + distance, 30, now=duration)
    assert result['classification'] == 'TAP'
    assert result['duration_ms'] == duration * 1000
    assert result['duration_used_for_classification'] is False


@pytest.mark.parametrize('delta', [(12, 0), (-12, 0), (0, 12), (0, -12), (6, 6)])
def test_crossing_system_slop_is_irreversible_even_if_returned_to_origin(delta):
    intent = TouchIntent(0, 0, 8, started=0)
    assert intent.move(*delta) == 'SWIPE'
    assert intent.finish(0, 0, now=0.4)['classification'] == 'SWIPE'


@pytest.mark.parametrize('slop', [0, -1, nan, inf])
def test_invalid_policy_fails_explicitly(slop):
    with pytest.raises(ValueError):
        TouchIntent(0, 0, slop)
