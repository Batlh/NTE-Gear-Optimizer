"""Reference values are source-exact; synthetic UI load cannot become GameData."""

from copy import deepcopy
from types import SimpleNamespace
from pathlib import Path
import ast
import importlib.util

import pytest

from nte_gear_optimizer_app.load_mode import LoadMode
from nte_gear_optimizer_app.reference_view import reference_sections, NOTICE
from nte_gear_optimizer_app.legacy_reference import (
    load_reference,
    load_extended_catalog,
)
from nte_gear_optimizer_app.viewmodel import ComparisonViewModel

ROOT = Path(__file__).resolve().parents[1]


def test_reference_every_numeric_record_and_set_is_visible_and_provenanced():
    ref = load_reference()
    sections = reference_sections(ref)
    assert [(key, len(rows)) for key, _, rows in sections] == [
        ('ark', 132),
        ('sets', 12),
        ('cartridges', 63),
        ('modules', 37),
    ]
    rendered = {key: detail for _, _, rows in sections for key, _, detail in rows}
    assert len(rendered) == 244
    for group in [
        'ArkExactPoints',
        'ArkObservedPoints',
        'CartridgeLevels',
        'ModuleEndpoints',
        'ModuleLevelSeries',
        'ModuleInGameSamples',
    ]:
        for row in ref[group]:
            text = rendered[row['RecordID']]
            assert NOTICE in text and row['SourceSHA256'] in text
            assert (
                row['SourceRelativePath'] in text
                and 'Zeile ' + str(row['SourceRow']) in text
            )
            original = row['Original']
            fields = {
                'ArkExactPoints': ['MainStatValue', 'SecondaryValue', 'Level'],
                'ArkObservedPoints': ['MainStatValue', 'SecondaryValue', 'Level'],
                'CartridgeLevels': ['Value', 'ItemLevel'],
                'ModuleEndpoints': ['FlatATK', 'FlatHP', 'EnhancementLevel'],
                'ModuleInGameSamples': ['MainATK', 'MainHP', 'ItemLevel'],
                'ModuleLevelSeries': [],
            }[group]
            for key in fields:
                if original.get(key):
                    assert original[key] in text
            if group == 'ModuleLevelSeries':
                for i, value in enumerate(
                    original['ValueSequence_L0_to_L20'].split(','),
                    int(original['LevelStart']),
                ):
                    assert f'Lv {i}: {value}' in text
    for row in ref['Sets']:
        text = rendered[row['SetID']]
        assert row['SetName'] in text and NOTICE in text
        for effect in ref['SetEffects']:
            if effect['RecordID'] in row['EffectRecordIDs']:
                assert (
                    effect['Original']['RawSummary'] in text
                    and effect['SourceSHA256'] in text
                )


@pytest.mark.parametrize(
    'metadata',
    [
        {},
        {'test_build': False},
        {'test_build': 'true'},
        {'test_build': 1},
        {'emulator_test_only': True},
    ],
)
def test_load_mode_is_unavailable_without_explicit_test_build(metadata):
    mode = LoadMode(metadata)
    assert not mode.available and not mode.set_enabled(True)
    assert mode.ark_rows(load_extended_catalog()['Arks']) == []
    assert mode.inventory_rows() == []
    mode.select('TEST_LOAD_ARK_299')
    assert mode.choice is None


def test_load_data_is_synthetic_and_cannot_change_catalog_or_viewmodel():
    cat = load_extended_catalog()
    before = deepcopy(cat)
    vm = ComparisonViewModel(cat)
    vm_before = deepcopy(vm.__dict__)
    mode = LoadMode({'test_build': True})
    rows = mode.ark_rows(cat['Arks'])
    items = mode.inventory_rows()
    assert len(rows) == 300 and len(items) == 100
    assert len({key for _, key in rows + items}) == 400
    assert all('nur Belastungstest' in title and 'Typ:' in title for title, _ in rows)
    mode.select(rows[-1][1])
    assert mode.choice == 'TEST_LOAD_ARK_299'
    mode.select(items[-1][1])
    assert mode.choice == 'TEST_LOAD_ITEM_099'
    mode.set_enabled(True)
    mode.values[(0, 'before', 'ScaleDirect')] = '999'
    assert cat == before and vm.__dict__ == vm_before
    with pytest.raises(ValueError):
        mode.select(cat['Arks'][0]['ArkID'])


def test_actual_reference_library_callback_is_read_only_and_detail_scrollable():
    tree = ast.parse(
        (ROOT / 'src/nte_gear_optimizer_app/app.py').read_text(encoding='utf-8')
    )
    app = next(
        n
        for n in tree.body
        if isinstance(n, ast.ClassDef) and n.name == 'ComparisonApp'
    )
    methods = {n.name: n for n in app.body if isinstance(n, ast.FunctionDef)}
    assert 'ResponsiveScrollView' in ast.unparse(methods['show_reference_detail'])
    for name in [
        'open_legacy_library',
        'show_reference_detail',
        'open_load_list',
        'load_fields_screen',
    ]:
        for node in ast.walk(methods[name]):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {
                    'choose_ark',
                    'choose_character',
                    'set_value',
                    'zero_group',
                    'calculate',
                }
    assert 'load_mode.values' in ast.unparse(methods['load_fields_screen'])


def test_current_editor_input_type_never_uses_historical_text_input():
    spec = importlib.util.spec_from_file_location(
        'ime_current', ROOT / 'tools/android_ime_state.py'
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    text = 'old inputType=0x1\n  mInputEditorInfo:\n    inputType=0x3002 imeOptions=0x12000000\n'
    assert mod.current_editor_input_type(text) == 12290
    assert mod.current_editor_input_type(text.replace('0x3002', '0x2')) == 2
    for invalid in ['inputType=0x3002', text + text]:
        with pytest.raises(ValueError):
            mod.current_editor_input_type(invalid)
