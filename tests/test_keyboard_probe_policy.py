from nte_gear_optimizer_app.keyboard_probe_policy import should_poll
import pytest


@pytest.mark.parametrize(
    'scrolling,focused,state,expected',
    [
        (True, False, {'ime_visible': False}, False),
        (False, False, {'ime_visible': False}, True),
        (True, True, {'ime_visible': False}, True),
        (True, False, {'ime_visible': True}, True),
        (True, False, {'ime_visible': None}, True),
        (True, False, None, True),
        (True, False, 'unavailable', True),
    ],
)
def test_diagnostic_poll_boundary(scrolling, focused, state, expected):
    assert (
        should_poll(scrolling=scrolling, focused=focused, last_state=state) is expected
    )
