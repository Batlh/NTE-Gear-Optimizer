"""Exercise production recycled-row methods without opening a local window."""

import ast
from pathlib import Path
from types import SimpleNamespace
from weakref import ref

from nte_gear_optimizer_app.legacy_reference import (
    ark_display_name,
    filter_arks,
    load_extended_catalog,
)
from nte_gear_optimizer_app.viewmodel import ComparisonViewModel

ROOT = Path(__file__).resolve().parents[1]


class DataBehavior:
    def refresh_view_attrs(self, rv, index, data):
        for key, value in data.items():
            setattr(self, key, value)


class FakeButton:
    def __init__(self, **kwargs):
        self.state = 'normal'
        for key, value in kwargs.items():
            setattr(self, key, value)

    def bind(self, **kwargs):
        pass


def row_class():
    source = (ROOT / 'src/nte_gear_optimizer_app/recycled_selector.py').read_text(
        encoding='utf-8'
    )
    node = next(
        n
        for n in ast.parse(source).body
        if isinstance(n, ast.ClassDef) and n.name == 'SelectorRow'
    )
    namespace = {
        'RecycleDataViewBehavior': DataBehavior,
        'DesignButton': FakeButton,
        'ObjectProperty': lambda *a, **k: None,
        'StringProperty': lambda *a, **k: '',
        'sp': lambda v: v,
        'dp': lambda v: v,
    }
    exec(
        compile(
            ast.Module(body=[node], type_ignores=[]), '<production SelectorRow>', 'exec'
        ),
        namespace,
    )
    return namespace['SelectorRow']


def setup_row(value='A', index=0):
    selected = []
    owner = SimpleOwner(selected)
    row = row_class()()
    data = {'value': value, 'name': 'First', 'text': 'First', 'owner': ref(owner)}
    row.refresh_view_attrs(owner, index, data)
    return row, owner, selected


class SimpleOwner:
    def __init__(self, selected):
        self.trace = None
        self.performance = None
        self.select_callback = selected.append


def test_same_recycled_identity_selects_once_and_resets_press():
    row, owner, selected = setup_row()
    row.on_press()
    row.on_release()
    row.on_release()
    assert selected == ['A']
    assert not row.press_valid


def test_held_press_never_selects_another_or_rebound_original_id():
    row, owner, selected = setup_row()
    row.on_press()
    row.refresh_view_attrs(
        owner,
        1,
        {'value': 'B', 'name': 'Second', 'text': 'Second', 'owner': ref(owner)},
    )
    row.on_release()
    assert selected == [] and row.state == 'normal'
    row.on_press()
    row.refresh_view_attrs(
        owner, 0, {'value': 'A', 'name': 'First', 'text': 'First', 'owner': ref(owner)}
    )
    row.refresh_view_attrs(
        owner,
        1,
        {'value': 'B', 'name': 'Second', 'text': 'Second', 'owner': ref(owner)},
    )
    row.on_release()
    assert selected == []


def test_none_is_an_explicit_valid_choice_but_closed_owner_cannot_select():
    row, owner, selected = setup_row(None)
    row.on_press()
    row.on_release()
    assert selected == [None]
    owner.select_callback = None
    row.on_press()
    row.on_release()
    assert selected == [None]


def test_recycled_row_releases_dead_owner_and_handles_large_identity_space():
    row, owner, selected = setup_row()
    for i in range(300):
        row.refresh_view_attrs(
            owner,
            i,
            {
                'value': str(i),
                'name': f'Entry {i}',
                'text': f'Entry {i}',
                'owner': ref(owner),
            },
        )
    assert row.option_index == 299 and row.name == 'Entry 299'
    row.on_press()
    row.on_release()
    assert selected == ['299']
    del owner
    assert row.owner() is None
    row.on_press()
    row.on_release()
    assert selected == ['299']


def test_current_app_constructor_and_selection_use_approved_unfiltered_catalog():
    source = (ROOT / 'src/nte_gear_optimizer_app/app.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    app = next(
        n
        for n in tree.body
        if isinstance(n, ast.ClassDef) and n.name == 'ComparisonApp'
    )
    ctor = next(
        n for n in app.body if isinstance(n, ast.FunctionDef) and n.name == '__init__'
    )
    # Execute the actual constructor with a GUI-free base, not a mirrored loader.
    ctor_cls = ast.ClassDef(
        name='ComparisonApp',
        bases=[ast.Name(id='Base', ctx=ast.Load())],
        keywords=[],
        body=[ctor],
        decorator_list=[],
    )
    namespace = {
        'Base': FakeButton,
        'ComparisonViewModel': ComparisonViewModel,
        'load_extended_catalog': load_extended_catalog,
    }
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[ctor_cls], type_ignores=[])),
            '<production app constructor>',
            'exec',
        ),
        namespace,
    )
    instance = namespace['ComparisonApp']()
    assert len(instance.vm.catalog['Arks']) == 51
    for character in [None] + [
        r['CharacterID'] for r in instance.vm.catalog['Characters']
    ]:
        rows, status = filter_arks(
            instance.vm.catalog['Arks'], character, instance.character_ark_type_mappings
        )
        assert len(rows) == 51 and status == 'NO_VERIFIED_CHARACTER_TYPE_SHOW_ALL'
        for row in rows:
            shown = ark_display_name(row)
            assert row['ArkType'] in shown and row['ArkName'] in shown
    selection = next(
        n for n in app.body if isinstance(n, ast.FunctionDef) and n.name == 'selection'
    )
    assert any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == 'ark_display_name'
        for n in ast.walk(selection)
    )
    assert any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == 'filter_arks'
        for n in ast.walk(selection)
    )
