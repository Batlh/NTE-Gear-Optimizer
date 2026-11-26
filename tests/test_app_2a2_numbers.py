from nte_gear_optimizer_app.viewmodel import normalize, numeric_hint, InputFormatError
import pytest


@pytest.mark.parametrize(
    'raw,expected,hint',
    [
        ('2,560', '2.56', 'übernommen als 2,56'),
        ('1,005', '1.005', 'übernommen als 1,005'),
        ('2 560', '2560', 'übernommen als 2560'),
        ('12 345,5', '12345.5', 'übernommen als 12345,5'),
        ('1,5', '1.5', ''),
        ('2560', '2560', ''),
    ],
)
def test_visible_interpretation(raw, expected, hint):
    assert normalize(raw) == expected
    assert numeric_hint(raw) == hint


@pytest.mark.parametrize(
    'raw', ['1 5', '12 34', '1 234 56', '1\t234', '1\u00a0234', '1 234.5']
)
def test_malformed_spaces_are_local_help(raw):
    with pytest.raises(InputFormatError):
        normalize(raw)
    assert numeric_hint(raw)
