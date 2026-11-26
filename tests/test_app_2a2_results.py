from test_viewmodel import ready_model
from nte_gear_optimizer_app.viewmodel import ComparisonViewModel


def test_missing_current_goes_first_and_jump_retains_inputs():
    vm = ready_model()
    vm.set_value('current', 'UniversalPP', '')
    vm.calculate()
    summary = vm.compact_display()
    assert summary.index('Was fehlt') < summary.index('Geänderte Werte')
    assert any(
        step == 1 and any('Universeller' in msg for msg in messages)
        for step, messages in vm.missing_groups()
    )
    before = (dict(vm.current), dict(vm.item_x), dict(vm.item_y))
    vm.jump_to(1)
    assert vm.step == 1 and before == (vm.current, vm.item_x, vm.item_y)
    assert 'nicht angegeben → nicht angegeben' not in vm.clarification_display()


def test_part_missing_and_applicability_route_to_own_page():
    vm = ready_model()
    vm.set_value('x', 'UniversalPP', '')
    vm.calculate()
    assert any(step == 2 for step, _ in vm.missing_groups())
    vm.last_result['engine']['Diagnostics'] = ['Zweig 4: Wert fehlt: CritEligible']
    assert vm.missing_groups()[0][0] == 0
    assert 'Zweig 4: Wert fehlt: Krit-Anwendbarkeit' in vm.compact_display()


def test_ready_is_not_hidden_or_gated():
    vm = ready_model()
    assert vm.calculate()['engine']['Verdict'] == 'BETTER'
    assert vm.missing_groups() == []
    assert vm.compact_display().startswith('Besser\nVerhältnis: 1,100000000')


def test_every_catalog_entry_can_be_selected_without_id_changes():
    vm = ComparisonViewModel()
    for row in vm.catalog['Characters']:
        vm.choose_character(row['CharacterID'])
        assert vm.character_id == row['CharacterID']
        for p in vm.profiles():
            vm.choose_profile(p['BuildProfileID'])
            for b in vm.branches():
                vm.choose_branch(b['ComparisonBranchID'])
                assert vm.branch_id == b['ComparisonBranchID']
    for ark in vm.catalog['Arks']:
        vm.choose_ark(ark['ArkID'])
        assert vm.ark_id == ark['ArkID']


def test_part_only_percentage_never_invents_a_missing_current_value():
    vm = ready_model()
    vm.set_value('current', 'ScaleDirect', '')
    vm.calculate()
    line = next(
        line
        for line in vm.clarification_display().splitlines()
        if '(%) auf dem Teil:' in line
    )
    assert line == 'ANG (%) auf dem Teil: Teile 0 → 0'
