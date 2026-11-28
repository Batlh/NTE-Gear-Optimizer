"""Execute actual observer methods without importing or opening Kivy locally."""

import ast
from pathlib import Path
from types import SimpleNamespace

from nte_gear_optimizer_app.touch_intent import TouchIntent
from nte_gear_optimizer_app.scroll_observer import ScrollObserver


def method(filename, cls, name):
    path = Path(__file__).resolve().parents[1] / 'src/nte_gear_optimizer_app' / filename
    tree = ast.parse(path.read_text(encoding='utf-8'))
    classnode = next(
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls
    )
    function = next(
        n for n in classnode.body if isinstance(n, ast.FunctionDef) and n.name == name
    )
    function.decorator_list = []
    namespace = {'TouchIntent': TouchIntent}
    exec(
        compile(ast.Module(body=[function], type_ignores=[]), str(path), 'exec'),
        namespace,
    )
    return namespace[name]


def test_actual_contact_lifetime_ignores_hover_but_keeps_real_contact():
    handler = method('app.py', 'ComparisonApp', 'observe_touch_lifetime')
    app = SimpleNamespace(active_touches=set(), keyboard_viewport=None)
    hover = SimpleNamespace(uid=1, is_touch=False)
    real = SimpleNamespace(uid=2, is_touch=True)
    handler(app, None, 'begin', hover)
    assert app.active_touches == set()
    handler(app, None, 'begin', real)
    assert app.active_touches == {2}
    handler(app, None, 'update', hover)
    handler(app, None, 'end', real)
    assert app.active_touches == set()


def test_actual_scroll_observer_does_not_start_hover_gesture():
    clock = SimpleNamespace(
        schedule_interval=lambda *a: SimpleNamespace(cancel=lambda: None)
    )
    window = SimpleNamespace(
        width=100, height=100, bind=lambda **kw: None, unbind=lambda **kw: None
    )
    observer = ScrollObserver(window, clock, 'linux', lambda *a, **kw: None)
    observer.motion(None, 'begin', SimpleNamespace(uid=1, is_touch=False))
    assert observer.metrics.current is None
    real = SimpleNamespace(uid=2, is_touch=True, sx=0.2, sy=0.3)
    observer.motion(None, 'begin', real)
    assert observer.metrics.current['touch_id'] == '2'
    observer.motion(None, 'end', real)
    assert observer.metrics.current['released']
    observer.stop()


def test_actual_h01_trace_ignores_hover_and_keeps_tap():
    handler = method('touch_slop.py', 'TouchIntentObserver', 'motion')
    rows = []
    state = SimpleNamespace(
        window=SimpleNamespace(width=100, height=100),
        active={},
        recent=[],
        policy={'window_px': 8},
        emit=lambda event, **kw: rows.append((event, kw)),
    )
    handler(state, None, 'begin', SimpleNamespace(uid=1, is_touch=False))
    assert not state.active
    real = SimpleNamespace(uid=2, is_touch=True, sx=0.2, sy=0.3)
    handler(state, None, 'begin', real)
    real.sx += 0.01
    handler(state, None, 'update', real)
    handler(state, None, 'end', real)
    assert not state.active and len(rows) == 1
    assert rows[0][1]['touch_id'] == '2'
    assert rows[0][1]['classification'] == 'TAP'
