import ast
from pathlib import Path
from decimal import Decimal
import pytest
from nte_gear_optimizer_app.viewmodel import ComparisonViewModel, normalize
from nte_gear_optimizer.comparison.swap import compile_swap


def ready_model(kind='DAMAGE', scale='ANG'):
    vm = ComparisonViewModel()
    vm.choose_character('ELYMS')
    for key, value in {
        'ProfileType': kind,
        'ScalingStat': scale,
        'CritEligible': 'FALSE',
        'BreakEligible': 'FALSE',
        'CycleType': 'NONE',
    }.items():
        vm.set_override(key, value)
    for group in list(vm.groups()):
        vm.zero_group(group)
    for group in list(vm.groups(parts=True)):
        vm.zero_group(group, parts=True)
    vm.set_value('current', 'ScaleDirect', '100')
    vm.set_value('x', 'ScaleDirect', '10')
    vm.set_value('y', 'ScaleDirect', '20')
    return vm


@pytest.mark.parametrize(
    'raw,expected',
    [
        ('1,005', '1.005'),
        ('  12 ', '12'),
        ('-0', '0'),
        ('', None),
        ('  ', None),
        ('1 234,50', '1234.5'),
        ('1\u00a0234', '1234'),
    ],
)
def test_normalization(raw, expected):
    assert normalize(raw) == expected


@pytest.mark.parametrize('raw', ['1.234,5', 'NaN', 'Inf', '1,2,3', 'no'])
def test_invalid_input_is_not_a_silent_zero(raw):
    with pytest.raises(ValueError):
        normalize(raw)


def test_four_step_navigation_retains_input_and_never_blocks_irrelevant_missing_fields():
    vm = ready_model('HEAL', 'LP')
    vm.current['CritRatePP'] = 'bad irrelevant'
    assert 'CritRatePP' not in vm.fields()
    for i in range(3):
        vm.next()
    assert vm.step == 3 and vm.calculate()['engine']['Verdict'] == 'BETTER'
    vm.back()
    vm.next()
    assert vm.current['ScaleDirect'] == '100'


def test_bonus_default_empty_and_zero_is_explicit():
    vm = ComparisonViewModel()
    vm.set_override('ProfileType', 'DAMAGE')
    vm.set_override('ScalingStat', 'ANG')
    assert vm.current == {} and vm.item_x == {} and vm.item_y == {}
    vm.zero_group('bonus')
    assert vm.current['UniversalPP'] == '0'
    assert not vm.item_x
    vm.zero_group('bonus', parts=True)
    assert vm.item_y['ReductionPP'] == '0'


def test_swap_uses_current_including_x_without_double_count():
    r = ready_model().calculate()
    assert r['engine']['RawRatio'] == '1.1'
    assert r['engine']['Deltas']['ScaleDirect'] == '10'
    assert r['part_deltas']['ScaleDirect'] == '10'


def test_unknown_keeps_all_independent_values_and_deltas():
    vm = ready_model()
    vm.current['ScaleDirect'] = ''
    result = vm.calculate()
    assert result['engine']['Verdict'] is None
    assert result['part_deltas']['ScaleDirect'] == '10'
    assert result['current']['UniversalPP'] == '0' and 'Teil X' in vm.display()


def test_invalid_input_help_is_local():
    vm = ready_model()
    vm.current['UniversalPP'] = 'abc'
    result = vm.calculate()
    assert result['engine']['Verdict'] is None
    assert result['errors'] and result['part_deltas']['ScaleDirect'] == '10'
    assert 'Ungültige Zahl' in vm.display()


def test_white_basis_only_needed_for_changed_scaling_percentage():
    vm = ready_model()
    vm.item_y['ScalingPercentPP'] = '10'
    r = vm.calculate()
    assert r['engine']['Verdict'] is None
    assert r['part_deltas']['ScalingPercentPP'] == '10'
    vm.white_panel_base = '50'
    assert vm.calculate()['engine']['RawRatio'] == '1.15'
    vm.item_y['ScalingPercentPP'] = '0'
    vm.white_panel_base = ''
    assert vm.calculate()['engine']['RawRatio'] == '1.1'


def test_zero_negative_and_comma_critical_swap_match_contract():
    vm = ready_model()
    vm.item_x['ScaleDirect'] = '100'
    vm.item_y['ScaleDirect'] = '0'
    assert vm.calculate()['engine']['VerdictRatio'] == '0.000000000'
    vm.item_x['ScaleDirect'] = '1100'
    vm.item_y['ScaleDirect'] = '1'
    assert vm.calculate()['engine']['RawRatio'] is None
    vm = ready_model()
    vm.item_y['ScaleDirect'] = '10'
    vm.set_override('CritEligible', 'TRUE')
    vm.current.update(CritRatePP='50', CritDamagePP='100')
    vm.item_x.update(CritRatePP='0', CritDamagePP='0')
    vm.item_y.update(CritRatePP='10', CritDamagePP='0')
    assert vm.calculate()['engine']['VerdictRatio'] == '1.066666667'
    assert '1,066666667' in vm.display()


def test_source_unknowns_and_legacy_guide_notice():
    vm = ready_model()
    assert len(vm.catalog['Characters']) == 26
    vm.choose_ark('ARK_ECHOES_ON_HOLD')
    vm.ark_level = '79'
    assert 'Grundwert unbekannt' in vm.ark_summary()
    assert vm.calculate()['engine']['Verdict'] == 'BETTER'
    vm.ark_level = '80'
    assert '570' in vm.ark_summary()
    vm.choose_character('ADLER')
    vm.choose_profile('BUILD_ADLER_DEFAULT')
    assert any(
        r['SourceStatus'] == 'NOT_VERIFIED_FOR_1_5' for r in vm.catalog['GuideTargets']
    )
    assert 'für 1.5 nicht geprüft' in vm.display()


def test_identity_changes_cannot_reuse_another_characters_total_or_scale():
    vm = ready_model()
    vm.choose_character('ZERO')
    assert vm.current == {}
    vm = ready_model()
    vm.set_override('ScalingStat', 'LP')
    assert 'ScaleDirect' not in vm.current
    with pytest.raises(ValueError):
        vm.choose_character('bad')
    with pytest.raises(ValueError):
        vm.choose_profile('BUILD_ADLER_DEFAULT')
    with pytest.raises(ValueError):
        vm.choose_branch('bad')
    with pytest.raises(ValueError):
        vm.choose_ark('bad')


def test_viewmodel_and_core_have_no_kivy_dependency():
    root = Path(__file__).parents[1] / 'src'
    files = list((root / 'nte_gear_optimizer').rglob('*.py')) + [
        (root / 'nte_gear_optimizer_app/viewmodel.py')
    ]
    for p in files:
        if '_REV_' in p.name:
            continue
        for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))):
            if isinstance(n, ast.Import):
                assert not any(a.name.startswith('kivy') for a in n.names)
            if isinstance(n, ast.ImportFrom):
                assert not (n.module or '').startswith('kivy')


def test_known_irrelevant_values_remain_visible_without_becoming_required():
    vm = ready_model('HEAL', 'LP')
    vm.current['CritRatePP'] = '50'
    vm.item_x['CritRatePP'] = '10'
    vm.item_y['CritRatePP'] = '20'
    r = vm.calculate()
    assert r['engine']['Verdict'] == 'BETTER' and r['current']['CritRatePP'] == '50'
    assert r['part_deltas']['CritRatePP'] == '10' and 'Krit-Rate' in vm.display()


def test_after_totals_are_visible_and_invalid_ark_level_is_local():
    vm = ready_model()
    vm.choose_ark('ARK_ECHOES_ON_HOLD')
    vm.ark_level = 'bad'
    result = vm.calculate()
    assert result['resolved']['AfterScaleDirect'] == '110'
    assert 'Gesamtwerte nach dem Tausch' in vm.display()
    assert (
        'Ark-Level ungültig' in vm.display() and result['engine']['Verdict'] == 'BETTER'
    )


def test_white_basis_control_only_for_an_actual_percentage_change():
    vm = ready_model()
    assert not vm.needs_white_base()
    vm.item_y['ScalingPercentPP'] = '10'
    assert vm.needs_white_base()
    vm.item_x['ScalingPercentPP'] = '10'
    assert not vm.needs_white_base()


def test_after_heading_never_labels_y_as_x_and_retains_known_white_base():
    vm = ready_model()
    vm.white_panel_base = '50'
    vm.item_y['ScalingPercentPP'] = '10'
    text = vm.display()
    assert 'Gesamt-ANG mit Teil Y: 115' in text
    assert vm.last_result['white_panel_base'] == '50'


def test_distinct_branch_scaling_channels_never_share_one_generic_total():
    vm = ready_model()
    profile = {
        'BuildProfileID': 'test_profile',
        'CharacterID': 'ELYMS',
        'Name': 'test',
        'SourceStatus': 'TEST',
    }
    vm.catalog['Profiles'].append(profile)
    vm.catalog['Branches'].extend(
        [
            {
                'BuildProfileID': 'test_profile',
                'ComparisonBranchID': 'ang',
                'ProfileType': 'DAMAGE',
                'ScalingStat': 'ANG',
                'CritEligible': 'FALSE',
                'BreakEligible': 'FALSE',
                'CycleReactionType': 'NONE',
            },
            {
                'BuildProfileID': 'test_profile',
                'ComparisonBranchID': 'lp',
                'ProfileType': 'HEAL',
                'ScalingStat': 'LP',
            },
        ]
    )
    vm.profile_id = 'test_profile'
    vm.current['HealingPP'] = '0'
    vm.item_x['HealingPP'] = '0'
    vm.item_y['HealingPP'] = '0'
    assert vm.ambiguous_scaling() and 'ScaleDirect' not in vm.fields()
    result = vm.calculate()
    assert result['engine']['Verdict'] is None
    assert result['part_deltas']['ScaleDirect'] == '10'
    assert 'unterschiedliche Gesamtwerte' in vm.display()
