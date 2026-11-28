import gc
import threading
import weakref
from types import SimpleNamespace

import pytest

from nte_gear_optimizer_app.frame_attribution import Attribution, CATEGORIES, CAPACITY
from nte_gear_optimizer_app.frame_runtime_hooks import TimedCallback, RuntimeHooks


def test_nested_spans_partition_frame_without_double_counting():
    p = Attribution(lambda: True, lambda: 0)
    cb = p.name_id('scheduled.callback')
    p.span('clock', 0, 0.008, cb)
    p.span('input', 0.001, 0.006)
    p.span('gc', 0.002, 0.003, 2)
    p.span('draw', 0.006, 0.009)
    r = p.frame(0, 0.010)
    e = dict(zip(CATEGORIES, r['exclusive_ms']))
    assert e['gc'] == pytest.approx(1)
    assert e['input'] == pytest.approx(4)
    assert e['clock'] == pytest.approx(1)
    assert e['draw'] == pytest.approx(3)
    assert r['unassigned_ms'] == pytest.approx(1)
    assert sum(r['exclusive_ms']) + r['unassigned_ms'] == pytest.approx(10)
    assert r['clock_top5'] == [[cb, 1, 8]]
    assert r['input_calls'] == 1
    assert r['gc_events'] == [[2, pytest.approx(1)]]


def test_clipping_overflow_and_empty_frame_are_explicit():
    p = Attribution(lambda: True, lambda: 0)
    for _ in range(CAPACITY + 3):
        p.span('input', -1, 2)
    r = p.frame(0, 0.01)
    assert r['overflow'] == 3 and r['input_calls'] == CAPACITY + 3
    assert sum(r['exclusive_ms']) == pytest.approx(10)
    assert r['unassigned_ms'] == 0
    assert p.frame(1, 1.02)['unassigned_ms'] == 0  # Span remains active until t=2.
    assert p.frame(3, 3.02)['unassigned_ms'] == pytest.approx(20)


def test_gc_generations_and_callback_lifecycle():
    now = [0.0]
    p = Attribution(lambda: True, lambda: now[0])
    before = gc.callbacks[:]
    p.install_gc()
    p.install_gc()
    assert gc.callbacks.count(p.gc_hook) == 1
    for gen in range(3):
        p.gc_event('start', {'generation': gen})
        now[0] += 0.001
        p.gc_event('stop', {'generation': gen})
    r = p.frame(0, 0.01)
    assert r['gc_counts'] == [1, 1, 1]
    assert [e[0] for e in r['gc_events']] == [0, 1, 2]
    assert all(e[1] == pytest.approx(1) for e in r['gc_events'])
    p.stop()
    p.stop()
    assert gc.callbacks == before


def test_background_thread_does_not_pollute_ui_frame():
    p = Attribution(lambda: True, lambda: 0)
    t = threading.Thread(target=lambda: p.span('input', 0, 1))
    t.start()
    t.join()
    assert p.frame(0, 1)['input_calls'] == 0


def test_top_five_and_name_registry_are_bounded():
    p = Attribution(lambda: True, lambda: 0)
    for i in range(200):
        index = p.name_id(str(i))
        p.span('clock', 0, i / 1000, index)
    r = p.frame(0, 1)
    assert len(p.names) == 128 and len(r['clock_top5']) == 5
    assert r['clock_calls'] == 200


def test_clock_wrapper_keeps_return_exception_and_weak_bound_target():
    now = [0.0]
    p = Attribution(lambda: True, lambda: now[0])

    class Target:
        def callback(self, dt):
            now[0] += 0.002
            return dt

    target = Target()
    ref = weakref.ref(target)
    callback = TimedCallback(target.callback, p)
    assert callback == target.callback
    assert callback(0.4) == 0.4
    assert p.frame(0, 0.01)['clock_calls'] == 1
    del target
    gc.collect()
    assert ref() is None and callback(0.1) is False

    def fail(dt):
        raise ValueError('unchanged')

    bad = TimedCallback(fail, p)
    with pytest.raises(ValueError, match='unchanged'):
        bad(0)
    assert p.frame(0, 0.01)['clock_calls'] == 1


def test_clock_release_ref_false_keeps_target_and_disabled_is_transparent():
    p = Attribution(lambda: False, lambda: 0)
    target = SimpleNamespace()
    target.cb = lambda dt: 42
    callback = TimedCallback(target.cb, p, release_ref=False)
    assert callback(0) == 42
    assert p.frame(0, 1)['clock_calls'] == 0


def test_runtime_hooks_wrap_new_triggers_preserve_unschedule_and_restore():
    now = [0.0]
    p = Attribution(lambda: True, lambda: now[0])

    class Event:
        release_ref = True
        weak_callback = None

        def __init__(self, callback):
            self.callback = callback

        def get_callback(self):
            return self.callback

        def release(self):
            pass

    def cb(dt):
        now[0] += 0.001
        return False

    events = [Event(cb)]
    clock = SimpleNamespace(
        on_schedule=lambda ev: None,
        get_events=lambda: events,
        get_before_frame_events=lambda: [],
    )
    loop = SimpleNamespace(post_dispatch_input=lambda kind, touch: 'unchanged')

    class Label:
        texture = None

        def refresh(self):
            self.texture = object()

    original_refresh = Label.refresh
    original_input = loop.post_dispatch_input
    h = RuntimeHooks(SimpleNamespace(attribution=p), clock, loop, Label)
    assert isinstance(events[0].callback, TimedCallback)
    assert events[0].get_callback() == cb  # Clock.unschedule compares this way
    assert events[0].get_callback()(0) is False
    new = Event(cb)
    events.append(new)
    clock.on_schedule(new)
    clock.on_schedule(new)
    assert new.get_callback()(0) is False
    assert loop.post_dispatch_input('update', object()) == 'unchanged'
    label = Label()
    label.refresh()
    r = p.frame(0, 0.02)
    assert r['clock_calls'] == 2 and r['input_calls'] == 1
    assert r['texture_changes'] == 1
    h.stop()
    assert Label.refresh is original_refresh
    assert loop.post_dispatch_input is original_input
    assert events[0].callback == cb


def test_first_scroll_marker_ignores_taps_and_distinguishes_list():
    from nte_gear_optimizer_app.frame_profile import FrameProfiler

    now = [0.0]
    p = FrameProfiler(None, lambda: True, lambda: now[0])
    p.begin()  # Tap: no view and no presented frame
    p.finish()
    for label, first in [('step1', True), ('step1', False), ('selector_Ark', True)]:
        p.begin()
        p.note_view(label)
        now[0] += 0.01
        p.record(0)
        f = p.finish()
        assert f['attribution']['first_scroll_on_view'] is first
    p.stop()


def test_200_gestures_keep_attribution_bounded_and_errors_out_of_profile_log():
    import tracemalloc
    from nte_gear_optimizer_app.frame_profile import FrameProfiler
    from nte_gear_optimizer_app.scroll_metrics import ScrollMetrics

    now = [0.0]
    logged = []
    m = ScrollMetrics(
        lambda name, **kw: logged.append(kw), 120, clock=lambda: now[0], touch_slop=8
    )
    p = FrameProfiler(None, lambda: m.current is not None, lambda: now[0])
    m.profile = p
    tracemalloc.start()
    try:
        sizes = []
        for i in range(400):
            m.begin(str(i), 0, 0)
            m.move(str(i), 0, 20)
            for f in range(10):
                now[0] += 0.0084
                m.changed('step1', f * 10)
                m.frame()
                p.record(0.5)
            m.finish()
            # The journal mock is not the real bounded writer; clear it after
            # checking only the summaries/reference were sent, never raw data.
            assert 'frame_profile' not in logged[-1]
            logged.clear()
            if i in (199, 399):
                gc.collect()
                sizes.append(tracemalloc.get_traced_memory()[0])
        assert len(m.recent) == 100
        raw = [
            g['frame_profile']['attribution']['frames']
            for g in m.recent
            if 'frames' in g['frame_profile']['attribution']
        ]
        assert len(raw) == 5 and all(len(frames) == 10 for frames in raw)
        assert sizes[1] - sizes[0] < 256 * 1024, sizes
        assert len(p.attribution.starts) == CAPACITY
    finally:
        tracemalloc.stop()
        p.stop()


def test_weak_clock_callback_resolves_replaced_method_like_kivy():
    p = Attribution(lambda: False, lambda: 0)

    class Target:
        def method(self, dt):
            return 'old'

    target = Target()
    wrapped = TimedCallback(target.method, p)
    assert wrapped(0) == 'old'
    target.method = lambda dt: 'new'
    assert wrapped(0) == 'new'
    assert wrapped == target.method


def test_gc_during_attribution_is_carried_and_not_hidden():
    now = [1.01]
    p = Attribution(lambda: True, lambda: now[0])
    p.accounting = True
    p.gc_event('start', {'generation': 2})
    now[0] = 1.014
    p.gc_event('stop', {'generation': 2})
    p.accounting = False
    first = p.frame(1, 1.01)
    assert first['gc_events'] == []
    second = p.frame(1.01, 1.02)
    assert second['gc_events'] == [[2, pytest.approx(4)]]
    assert second['gc_counts'] == [0, 0, 1]
    assert second['unassigned_ms'] == pytest.approx(6)


def test_worker_gc_is_bounded_and_attributed_to_its_actual_interval():
    now = [1.002]
    p = Attribution(lambda: True, lambda: now[0])

    def worker():
        p.gc_event('start', {'generation': 0})
        now[0] = 1.005
        p.gc_event('stop', {'generation': 0})

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()
    r = p.frame(1, 1.01)
    assert r['gc_events'] == [[0, pytest.approx(3)]]
    assert r['gc_counts'] == [1, 0, 0]
    assert r['gc_off_ui_events'] == 1
    assert r['unassigned_ms'] == pytest.approx(7)


def test_idle_wait_and_input_poll_are_observed_without_changing_results():
    now = [0.0]
    p = Attribution(lambda: True, lambda: now[0])

    def idle():
        now[0] += 0.003
        return 'same_idle_result'

    def poll():
        now[0] += 0.001
        return 'same_poll_result'

    clock = SimpleNamespace(
        on_schedule=lambda ev: None,
        get_events=lambda: [],
        get_before_frame_events=lambda: [],
        idle=idle,
    )
    loop = SimpleNamespace(post_dispatch_input=lambda *a: None, dispatch_input=poll)

    class Label:
        def refresh(self):
            pass

    hooks = RuntimeHooks(SimpleNamespace(attribution=p), clock, loop, Label)
    assert clock.idle() == 'same_idle_result'
    assert loop.dispatch_input() == 'same_poll_result'
    f = p.frame(0, 0.01)
    values = dict(zip(CATEGORIES, f['exclusive_ms']))
    assert values['clock_idle'] == pytest.approx(3)
    assert values['input_poll'] == pytest.approx(1)
    assert f['unassigned_ms'] == pytest.approx(6)
    hooks.stop()
    assert clock.idle is idle and loop.dispatch_input is poll


@pytest.mark.parametrize(
    'enabled,gesture,expected',
    [
        (False, {'slop_crossed': 1}, False),
        (True, None, False),
        (True, {'slop_crossed': None}, False),
        (True, {'slop_crossed': 0.0}, True),
        (True, {'slop_crossed': 1, 'released': True}, True),
    ],
)
def test_ci_snapshot_quiet_only_during_real_scroll_or_inertia(
    enabled, gesture, expected
):
    from nte_gear_optimizer_app.android_ci import should_defer_snapshot

    assert should_defer_snapshot(enabled, gesture) is expected
