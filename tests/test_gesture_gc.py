import pytest
from nte_gear_optimizer_app.gesture_gc import GestureGCPolicy


class GC:
    def __init__(self, enabled=True, frozen=0):
        self.enabled, self.frozen = enabled, frozen
        self.calls = []

    def isenabled(self):
        return self.enabled

    def disable(self):
        self.calls.append('disable')
        self.enabled = False

    def enable(self):
        self.calls.append('enable')
        self.enabled = True

    def freeze(self):
        self.calls.append('freeze')
        self.frozen = 123

    def unfreeze(self):
        self.calls.append('unfreeze')
        self.frozen = 0

    def get_freeze_count(self):
        return self.frozen

    def get_count(self):
        return (0, 0, 0)

    def collect(self, gen):
        self.calls.append(('collect', gen))
        return 7


def test_base_default_has_no_process_gc_side_effect():
    gc = GC()
    p = GestureGCPolicy(lambda: False, api=gc)
    p.idle()
    p.begin()
    p.end()
    p.stop()
    assert gc.calls == []


@pytest.mark.parametrize(
    'mode,freeze,defer',
    [
        ('BASE', False, False),
        ('FREEZE', True, False),
        ('DEFER', False, True),
        ('BOTH', True, True),
    ],
)
def test_modes_are_independently_comparable_and_reversible(mode, freeze, defer):
    gc = GC()
    busy = [False]
    p = GestureGCPolicy(lambda: busy[0], api=gc)
    p.request_mode(mode)
    p.idle()
    assert p.freeze_owned is freeze
    assert gc.calls.count(('collect', 2)) == 1
    busy[0] = True
    p.begin()
    p.begin()
    assert p.pause_owned is defer
    assert gc.isenabled() is (not defer)
    p.idle()  # Never collect, freeze or flush while scrolling.
    assert gc.calls.count(('collect', 2)) == 1
    busy[0] = False
    p.end()
    p.idle()
    assert gc.isenabled() and not p.pause_owned
    assert gc.calls.count(('collect', 2)) == (2 if defer else 1)
    p.stop()
    assert gc.frozen == 0


def test_mode_change_is_deferred_until_idle():
    gc = GC()
    busy = [True]
    p = GestureGCPolicy(lambda: busy[0], api=gc)
    p.request_mode('BOTH')
    p.idle()
    assert p.mode == 'BASE' and gc.calls == []
    busy[0] = False
    p.idle()
    assert p.mode == 'BOTH' and p.freeze_owned
    p.stop()


def test_external_disabled_gc_and_external_freeze_are_preserved():
    gc = GC(enabled=False)
    p = GestureGCPolicy(lambda: False, api=gc)
    p.request_mode('BOTH')
    p.idle()
    p.begin()
    p.end()
    p.stop()
    assert not gc.enabled and gc.calls == []
    gc = GC(frozen=22)
    p = GestureGCPolicy(lambda: False, api=gc)
    p.request_mode('FREEZE')
    p.idle()
    p.stop()
    assert gc.frozen == 22 and 'unfreeze' not in gc.calls


def test_stop_restores_owned_pause_even_without_touch_release():
    gc = GC()
    busy = [False]
    p = GestureGCPolicy(lambda: busy[0], api=gc)
    p.request_mode('BOTH')
    p.idle()
    busy[0] = True
    p.begin()
    p.stop()
    assert gc.enabled and gc.frozen == 0
    assert not p.pause_owned and p.closed


def test_invalid_mode_cannot_change_gc():
    gc = GC()
    p = GestureGCPolicy(lambda: False, api=gc)
    with pytest.raises(ValueError):
        p.request_mode('M9')
    assert gc.calls == []


def test_200_gestures_collect_at_idle_and_keep_history_bounded():
    gc = GC()
    busy = [False]
    now = [0.0]
    p = GestureGCPolicy(lambda: busy[0], api=gc, clock=lambda: now[0])
    p.request_mode('BOTH')
    p.idle()
    for _ in range(200):
        busy[0] = True
        p.begin()
        now[0] += 0.5
        p.idle()
        busy[0] = False
        p.end()
        p.idle()
    assert p.deferred_gestures == 200
    assert p.freeze_calls == 1 and p.idle_collections == 201
    assert len(p.operations) == 32
    assert p.snapshot()['max_pause_ms'] == pytest.approx(500)
    p.stop()


def test_other_contact_keeps_pause_until_all_contacts_and_inertia_finish():
    gc = GC()
    busy = [False]
    p = GestureGCPolicy(lambda: busy[0], api=gc)
    p.request_mode('DEFER')
    p.idle()
    busy[0] = True
    p.begin()
    p.end()
    p.idle()
    assert p.pause_owned and not gc.enabled
    busy[0] = False
    p.idle()
    assert not p.pause_owned and gc.enabled
    assert p.idle_collections == 2
    p.stop()
