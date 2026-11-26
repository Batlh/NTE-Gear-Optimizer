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
    assert result['current']['UniversalPP'] == '0' and 'Aktuelles Teil' in vm.display()


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
    assert 'Gesamt-ANG mit neuem Teil: 115' in text
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


def test_branch_missing_values_and_fixed_offset_hint_reach_visible_result():
    vm = ready_model()
    vm.catalog['Profiles'].append(
        {
            'BuildProfileID': 'test_offset',
            'CharacterID': 'ELYMS',
            'Name': 'Test',
            'SourceStatus': 'TEST',
        }
    )
    vm.catalog['Branches'].append(
        {
            'BuildProfileID': 'test_offset',
            'ComparisonBranchID': 'b',
            'ProfileType': 'DAMAGE',
            'ScalingStat': 'ANG',
            'CritEligible': 'FALSE',
            'BreakEligible': 'FALSE',
            'CycleReactionType': 'NONE',
            'FixedOffsetStatus': 'UNKNOWN',
        }
    )
    vm.profile_id = 'test_offset'
    vm.branch_id = 'b'
    vm.overrides = {}
    assert 'Der feste Anteil dieses Zweigs ist unbekannt' in vm.display()
    vm.set_value('current', 'ScaleDirect', '')
    assert 'Zweig 1:' in vm.display()
    assert 'fehlen relevante Angaben' in vm.display()


def test_all_bundled_profiles_and_branches_can_display_missing_inputs_without_crash():
    vm = ComparisonViewModel()
    for profile in vm.catalog['Profiles']:
        vm.choose_character(profile['CharacterID'])
        vm.choose_profile(profile['BuildProfileID'])
        for branch in [None] + [r['ComparisonBranchID'] for r in vm.branches()]:
            vm.choose_branch(branch)
            assert vm.display()


@pytest.mark.parametrize('value', ['2.560', '12.345', '1.234.567', '-2.560', '1.234,5'])
def test_thousands_point_requires_local_help_without_interpretation(value):
    from nte_gear_optimizer_app.viewmodel import InputFormatError, numeric_hint
    from nte_gear_optimizer_app import texts as T

    with pytest.raises(InputFormatError) as error:
        normalize(value)
    assert error.value.hint == numeric_hint(value) == T.THOUSANDS_HINT


@pytest.mark.parametrize(
    'raw,expected', [('1,5', '1.5'), ('2560', '2560'), ('2,560', '2.56')]
)
def test_german_decimal_and_plain_integer_are_unambiguous(raw, expected):
    assert normalize(raw) == expected


def test_other_points_are_rejected_consistently_with_comma_help():
    from nte_gear_optimizer_app.viewmodel import numeric_hint
    from nte_gear_optimizer_app import texts as T

    with pytest.raises(ValueError):
        normalize('1.5')
    assert numeric_hint('1.5') == T.DECIMAL_HINT


def test_ambiguous_active_value_keeps_local_raw_help_and_independent_delta():
    from nte_gear_optimizer_app import texts as T

    vm = ready_model()
    vm.set_value('current', 'ScaleDirect', '2.560')
    result = vm.calculate()
    assert result['engine']['Verdict'] is None
    assert list(result['errors'].values()) == [T.THOUSANDS_HINT]
    assert result['part_deltas']['ScaleDirect'] == '10'
    compact = vm.compact_display()
    assert (
        '2.560' + T.UNPARSED in vm.clarification_display()
        and T.THOUSANDS_HINT in compact
    )
    assert 'Δ 10' in compact


def test_irrelevant_ambiguous_value_is_not_a_global_gate():
    vm = ready_model()
    vm.set_value('current', 'CritRatePP', '2.560')
    assert vm.calculate()['engine']['Verdict'] == 'BETTER'
    assert not vm.last_result['errors']


def test_compact_result_prioritizes_verdict_ratio_changes_and_hides_unchanged_zeros():
    vm = ready_model()
    compact = vm.compact_display()
    assert compact.startswith('Besser\nVerhältnis: 1,100000000')
    assert 'ANG: 100 → 110 (Δ 10)' in compact
    assert 'Universeller Bonus (%): 0' not in compact
    assert 'Universeller Bonus (%): 0' not in vm.details_display(False)
    assert 'Universeller Bonus (%): 0' in vm.details_display(True)


def test_changed_zero_after_remains_visible_and_unknown_explanation_keeps_zero_baselines():
    vm = ready_model()
    vm.set_value('x', 'ScaleDirect', '100')
    vm.set_value('y', 'ScaleDirect', '0')
    assert 'ANG: 100 → 0 (Δ -100)' in vm.compact_display()
    vm = ready_model()
    vm.set_value('current', 'ScaleDirect', '')
    compact = vm.compact_display()
    assert 'Was fehlt' in compact and 'Werte zur Klärung' not in compact
    assert (
        'Universeller Bonus (%): aktuell 0 · Teile 0 → 0' in vm.clarification_display()
    )
    assert 'Universeller Bonus (%): 0' in vm.details_display(False)


def test_visible_names_and_debug_probe_gate():
    from nte_gear_optimizer_app import texts as T

    assert T.LOGO == 'Aktuelles Teil ↔ Neues Teil'
    assert (
        'Teil X' not in ready_model().display()
        and 'Teil Y' not in ready_model().display()
    )
    assert T.footer(False, True) == T.footer(True, False) == T.SESSION
    assert T.footer(True, True) == T.FONT_PROBE
