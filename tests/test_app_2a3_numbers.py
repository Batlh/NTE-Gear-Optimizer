import pytest

from nte_gear_optimizer_app.viewmodel import (
    ARK_LEVEL_HINT,
    ark_level_hint,
    normalize,
    numeric_hint,
    InputFormatError,
)
from test_viewmodel import ready_model


@pytest.mark.parametrize('space', [' ', '\u00a0', '\u202f'])
def test_grouping_spaces_identical(space):
    raw = '2' + space + '560'
    assert normalize(raw) == '2560'
    assert numeric_hint(raw) == 'übernommen als 2560'
    assert normalize('1' + space + '234' + space + '567,5') == '1234567.5'
    with pytest.raises(InputFormatError):
        normalize('25' + space + '60')


@pytest.mark.parametrize(
    'raw', ['80,8', '80.8', '80 8', '80ü8', '80😝8', '0', '81', '-1', 'abc', '25😝60']
)
@pytest.mark.parametrize('selected', [False, True])
def test_bad_level_local_help_even_without_ark(raw, selected):
    vm = ready_model()
    if selected:
        vm.choose_ark('ARK_ECHOES_ON_HOLD')
    vm.ark_level = raw
    assert ark_level_hint(raw) == ARK_LEVEL_HINT
    assert 'Ark-Level ungültig' in vm.ark_summary()
    assert vm.calculate()['engine']['Verdict'] == 'BETTER'
    vm.current['ScaleDirect'] = ''
    vm.calculate()
    assert any(
        step == 0 and any('nicht übernommen' in line for line in lines)
        for step, lines in vm.missing_groups()
    )


@pytest.mark.parametrize('raw', ['080', '80', '1', ''])
def test_level_ascii_integer_and_empty(raw):
    assert ark_level_hint(raw) == ''
    vm = ready_model()
    vm.choose_ark('ARK_ECHOES_ON_HOLD')
    vm.ark_level = raw
    assert 'ungültig' not in vm.ark_summary()
    if raw in ('080', '80'):
        assert '570' in vm.ark_summary()


def test_missing_field_one_row_and_reason_once():
    from nte_gear_optimizer_app import texts as T

    vm = ready_model()
    vm.current['UniversalPP'] = ''
    result = vm.calculate()
    result['engine']['Diagnostics'] += [
        'Wert fehlt: BeforeUniversalPP',
        'Aktuell: UniversalPP fehlt',
    ]
    lines = dict(vm.missing_groups())[1]
    assert sum('Universeller Bonus' in line for line in lines) == 1
    summary = vm.compact_display()
    reason = T.STATUS_HINTS.get(
        result['engine']['OutputStatus'], T.MESSAGES['status_unknown']
    )
    assert summary.count(reason) == 1


def test_emoji_numeric_field_not_accepted():
    with pytest.raises(ValueError):
        normalize('25😝60')
    assert numeric_hint('25😝60')
