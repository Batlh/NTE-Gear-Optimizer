from types import SimpleNamespace

import pytest

from nte_gear_optimizer_app.diagnostic_trace import InputTrace


class Widget:
    def __init__(self, result=True):
        self.uid = 1
        self.parent = None
        self.opacity = 1
        self.width = 50
        self.height = 50
        self.disabled = False
        self.pos = (0, 0)
        self.size = (50, 50)
        self.result = result
        self.calls = 0

    def walk(self):
        yield self

    def to_window(self, *position):
        return position

    def on_touch_down(self, touch):
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.mark.parametrize('accepted', [True, False])
def test_trace_preserves_dispatch_even_if_sink_fails(accepted):
    w = Widget(accepted)
    app = SimpleNamespace(inputs={('current', 'ScaleDirect'): w}, root_box=w)

    def broken(row):
        raise OSError('diagnostic storage unavailable')

    trace = InputTrace(app, broken)
    trace.attach_tree(w)
    trace.attach_tree(w)
    touch = SimpleNamespace(uid='real-chain', pos=(10, 10), device='test')
    assert w.on_touch_down(touch) is accepted
    assert w.calls == 1
    assert len(trace.events) == int(accepted)
    if accepted:
        assert trace.events[0]['widget']['field'] == 'current:ScaleDirect'


def test_trace_does_not_swallow_application_exception():
    w = Widget(ValueError('actual application error'))
    trace = InputTrace(SimpleNamespace(inputs={}, root_box=w), lambda row: None)
    trace.attach_tree(w)
    with pytest.raises(ValueError, match='actual application error'):
        w.on_touch_down(SimpleNamespace(uid='1', pos=(0, 0)))


def test_trace_memory_bound_and_detached_visibility():
    root = Widget()
    detached = Widget()
    trace = InputTrace(SimpleNamespace(inputs={}, root_box=root), lambda row: None)
    assert not trace.describe(detached)['tree_visible']
    for i in range(10_000):
        trace.emit('motion', value=i)
    assert len(trace.events) == 2000
