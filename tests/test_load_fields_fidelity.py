"""Actual synthetic field builder: hints/comma/focus without a local GUI."""

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from nte_gear_optimizer_app.load_mode import LoadMode
from nte_gear_optimizer_app.viewmodel import numeric_hint

ROOT = Path(__file__).resolve().parents[1]


class FakeWidget:
    def __init__(self, **kwargs):
        self.bound = {}
        self.children = []
        self.texture_size = (0, 0)
        self._text = ''
        self.focus = False
        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, value):
        self._text = value
        for fn in self.bound.get('text', []):
            fn(self, value)

    def bind(self, **kwargs):
        for key, fn in kwargs.items():
            self.bound.setdefault(key, []).append(fn)

    def add_widget(self, w):
        self.children.append(w)

    def insert_text(self, v):
        self.text += v


class FakeApp:
    def __init__(self):
        self.load_mode = LoadMode({'test_build': True})
        self.load_fields = {}
        self.load_commas = {}
        self.inputs = {'actual': 'unchanged'}
        self.vm = SimpleNamespace(
            current={'ScaleDirect': '2560'},
            item_x={'ScaleDirect': '10'},
            item_y={'ScaleDirect': '20'},
        )
        self.keyboard_session = SimpleNamespace(focus_changed=lambda *a: None)

    def focus_scroll(self, *args):
        pass

    def button(self, text, callback):
        return SimpleNamespace(text=text, callback=callback)


def builder(platform):
    tree = ast.parse(
        (ROOT / 'src/nte_gear_optimizer_app/app.py').read_text(encoding='utf-8')
    )
    app = next(
        n
        for n in tree.body
        if isinstance(n, ast.ClassDef) and n.name == 'ComparisonApp'
    )
    method = next(
        n
        for n in app.body
        if isinstance(n, ast.FunctionDef) and n.name == 'load_text_input'
    )
    node = ast.ClassDef(
        name='FieldBuilder',
        bases=[ast.Name(id='FakeApp', ctx=ast.Load())],
        keywords=[],
        body=[method],
        decorator_list=[],
    )
    ns = {
        'FakeApp': FakeApp,
        'BoxLayout': FakeWidget,
        'DesignTextInput': FakeWidget,
        'Label': FakeWidget,
        'KIVY_PLATFORM': platform,
        'dp': lambda v: v,
        'sp': lambda v: v,
        'rgba': lambda v: (1, 1, 1, 1),
        'numeric_hint': numeric_hint,
    }
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
            '<actual load field builder>',
            'exec',
        ),
        ns,
    )
    return ns['FieldBuilder']()


@pytest.mark.parametrize('platform', ['android', 'win'])
def test_real_component_keeps_values_and_hints_separate_from_comparison(platform):
    app = builder(platform)
    key = (0, 'before', 'ScaleDirect')
    box = app.load_text_input(key)
    w = app.load_fields[key]
    assert len(box.children) == 2 and w._nte_hint.text == ''
    assert w.keyboard_mode == ('managed' if platform == 'android' else 'auto')
    assert w.input_type == ('number' if platform == 'android' else 'text')
    w.text = '2.560'
    assert 'Tausenderpunkt' in w._nte_hint.text
    assert app.load_mode.values[key] == '2.560'
    assert app.inputs == {'actual': 'unchanged'}
    assert app.vm.current == {'ScaleDirect': '2560'}
    assert app.vm.item_x == {'ScaleDirect': '10'} and app.vm.item_y == {
        'ScaleDirect': '20'
    }
    assert (
        key in app.load_commas if platform == 'android' else key not in app.load_commas
    )


def test_actual_load_comma_button_preserves_focus_and_decimal_syntax():
    app = builder('android')
    key = (1, 'after', 'CritRatePP')
    app.load_text_input(key)
    w = app.load_fields[key]
    w.text = '1'
    app.load_commas[key].callback()
    w.insert_text('5')
    assert w.focus and w.text == '1,5'
    assert app.load_mode.values[key] == '1,5' and not w._nte_hint.text


def test_load_field_maps_are_retained_per_page_instead_of_accumulated_globally():
    tree = ast.parse(
        (ROOT / 'src/nte_gear_optimizer_app/app.py').read_text(encoding='utf-8')
    )
    app = next(
        n
        for n in tree.body
        if isinstance(n, ast.ClassDef) and n.name == 'ComparisonApp'
    )
    fields = next(
        n.value
        for n in app.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == 'PAGE_FIELDS' for t in n.targets)
    )
    assert {'load_fields', 'load_commas'}.issubset(ast.literal_eval(fields))
    render = next(
        n for n in app.body if isinstance(n, ast.FunctionDef) and n.name == 'render'
    )
    assert "'load_fields': {}" in ast.unparse(
        render
    ) and "'load_commas': {}" in ast.unparse(render)
