"""Headless execution of the actual button methods; no local Kivy window."""

import ast
from copy import deepcopy
from pathlib import Path
import hashlib
from types import SimpleNamespace

import pytest

from nte_gear_optimizer_app.motion_buffer import MotionBuffer
from nte_gear_optimizer_app.touch_intent import TouchIntent
from nte_gear_optimizer_app.frame_profile import FrameProfiler
from nte_gear_optimizer_app.gesture_gc import GestureGCPolicy

ROOT = Path(__file__).resolve().parents[1]
BASE = 'b0a2f75de87f3963fc73f03d25bff4eee1181fd1'
BUTTON_PATH = 'src/nte_gear_optimizer_app/design_widgets.py'


class ButtonBase:
    def __init__(self, uid, **kwargs):
        self.uid = uid
        self.state = 'normal'
        self.releases = 0

    def on_touch_down(self, touch):
        return True

    def on_touch_move(self, touch):
        return False

    def on_touch_up(self, touch):
        self.releases += 1
        return False


def button_class(source):
    tree = ast.parse(source)
    node = deepcopy(
        next(
            n
            for n in tree.body
            if isinstance(n, ast.ClassDef) and n.name == 'DesignButton'
        )
    )
    node.name = 'ButtonProbe'
    node.bases = [ast.Name(id='ButtonBase', ctx=ast.Load())]
    node.body = [
        n
        for n in node.body
        if isinstance(n, ast.FunctionDef)
        and n.name in ('__init__', 'on_touch_down', 'on_touch_move', 'on_touch_up')
    ]
    constructor = next(n for n in node.body if n.name == '__init__')
    prefix = []
    for statement in constructor.body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(t, ast.Attribute) and t.attr == 'fill' for t in statement.targets
        ):
            break
        prefix.append(statement)
    constructor.body = prefix  # Actual init prefix, before graphics access.
    ns = {
        '__name__': 'actual_button_method_probe',
        'ButtonBase': ButtonBase,
        'sp': lambda value: value,
        'TouchIntent': TouchIntent,
        'touch_slop_policy': lambda: {'window_px': 8},
    }
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
            '<actual-button-methods>',
            'exec',
        ),
        ns,
    )
    return ns['ButtonProbe']


def baseline_source():
    # Exact historical source from BASE:BUTTON_PATH. No Git/network needed
    # in shallow CI checkouts or a standalone source snapshot.
    payload = (ROOT / 'tests/fixtures/design_widgets_b0_source.py.txt').read_bytes()
    assert hashlib.sha256(payload).hexdigest().upper() == (
        'B4F342852444D535F352859852DA8E1965BA729B66ACDF7C6EE9F2351E630AC2'
    )
    return payload.decode('utf-8')


def current_source():
    return (ROOT / BUTTON_PATH).read_text(encoding='utf-8')


class UID:
    calls = 0

    def __str__(self):
        self.calls += 1
        return 'stable-widget'


def touch():
    return SimpleNamespace(x=0, y=0, ud={}, ungrab=lambda _: None)


def test_actual_button_move_formats_key_once_instead_of_per_event():
    old_uid, new_uid = UID(), UID()
    old = button_class(baseline_source())(uid=old_uid)
    new = button_class(current_source())(uid=new_uid)
    for button in (old, new):
        event = touch()
        button.on_touch_down(event)
        for _ in range(1000):
            button.on_touch_move(event)
        button.on_touch_up(event)
        assert button.releases == 1
    assert old_uid.calls == 1002
    assert new_uid.calls == 1


@pytest.mark.parametrize(
    'distance,released', [(0, True), (8, True), (8.001, False), (40, False)]
)
def test_actual_cached_button_keeps_exact_tap_and_swipe_boundary(distance, released):
    for source in (baseline_source(), current_source()):
        button = button_class(source)(uid=123456)
        event = touch()
        button.on_touch_down(event)
        event.x = distance
        button.on_touch_move(event)
        button.on_touch_up(event)
        assert button.releases == int(released)


def test_motion_pool_never_replaces_slots_and_snapshot_is_a_copy():
    pool = MotionBuffer(16)
    identities = tuple(id(row) for row in pool.rows)
    event = SimpleNamespace(sx=0, sy=0, x=0, y=0, device='SDL – Gerät')
    for i in range(1000):
        event.x = i
        pool.record('update', event)
    assert tuple(id(row) for row in pool.rows) == identities
    assert pool.count == 16
    snapshot = pool.snapshot()
    assert [r['x'] for r in snapshot] == list(range(984, 1000))
    event.x = 1000
    pool.record('end', event)
    assert snapshot[0]['x'] == 984 and snapshot[-1]['x'] == 999
    assert pool.snapshot()[-1]['event'] == 'end'
    assert pool.snapshot()[-1]['device'] == 'SDL – Gerät'


def test_unknown_device_is_not_formatted_or_serialized_per_move():
    class Device:
        def __str__(self):
            raise AssertionError('Must not format a device during motion')

    pool = MotionBuffer()
    pool.record('begin', SimpleNamespace(device=Device()))
    assert pool.snapshot()[0]['device'] == 'Device'


@pytest.mark.parametrize('capacity', [0, -1, True])
def test_invalid_motion_capacity_rejected(capacity):
    with pytest.raises(ValueError):
        MotionBuffer(capacity)


def test_new_modal_never_inherits_previous_roots_inventory():
    profile = FrameProfiler(None, lambda: False)
    try:
        profile.cached_inventory = {'page': 1, 'widgets': 99}
        profile.queue_inventory(object(), 'selector:Ark')
        actual = profile.finish()['inventory']
        assert actual['status'] == 'UNVERIFIED_PENDING_IDLE_SAMPLE'
        assert actual['requested_view'] == 'selector:Ark'
        assert 'widgets' not in actual
    finally:
        profile.stop()


def test_modal_inventory_waits_for_all_contacts_not_just_scroll_threshold():
    busy = [True]

    class Root:
        canvas = SimpleNamespace(children=[])
        walks = 0

        def walk(self):
            self.walks += 1
            return iter([self])

    root = Root()
    profile = FrameProfiler(None, lambda: False)
    profile.gc_policy = GestureGCPolicy(lambda: busy[0])
    try:
        profile.queue_inventory(root, 'selector:Ark')
        profile.idle_inventory()
        assert root.walks == 0
        busy[0] = False
        profile.idle_inventory()
        assert root.walks == 1
        assert profile.cached_inventory['page'] == 'selector:Ark'
        assert profile.cached_inventory['widgets'] == 1
    finally:
        profile.stop()


class ScrollBase:
    def __init__(self, uid):
        self.uid = uid
        self.cleared = 0

    def _get_uid(self, prefix='sv'):
        # Exact pinned upstream contract, not a replacement UI implementation.
        return '{0}.{1}'.format(prefix, self.uid)

    def clear_preview(self):
        self.cleared += 1

    def on_scroll_move(self, touch):
        return 'BASE_SCROLL_MOVE'

    def on_touch_move(self, touch):
        return 'BASE_TOUCH_MOVE'

    def on_scroll_stop(self, touch, check_children=True):
        return 'BASE_SCROLL_STOP'


def scroll_class():
    tree = ast.parse(
        (ROOT / 'src/nte_gear_optimizer_app/responsive_scroll.py').read_text(
            encoding='utf-8'
        )
    )
    node = deepcopy(
        next(
            n
            for n in tree.body
            if isinstance(n, ast.ClassDef) and n.name == 'ResponsiveScrollView'
        )
    )
    node.name = 'ScrollProbe'
    node.bases = [ast.Name(id='ScrollBase', ctx=ast.Load())]
    node.body = [
        n
        for n in node.body
        if isinstance(n, ast.FunctionDef)
        and n.name in ('_get_uid', 'on_scroll_move', 'on_scroll_stop', 'on_touch_move')
    ]
    ns = {'__name__': 'actual_scroll_method_probe', 'ScrollBase': ScrollBase}
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
            '<actual-scroll-methods>',
            'exec',
        ),
        ns,
    )
    return ns['ScrollProbe']


def test_actual_scroll_keys_preserve_upstream_prefixes_and_cache_hot_values():
    uid = UID()
    scroll = scroll_class()(uid)
    first = scroll._get_uid()
    avoid = scroll._get_uid('svavoid')
    for _ in range(1000):
        assert scroll._get_uid() is first
        assert scroll._get_uid('svavoid') is avoid
    assert first == 'sv.stable-widget' and avoid == 'svavoid.stable-widget'
    assert uid.calls == 2
    assert scroll._get_uid('future-prefix') == 'future-prefix.stable-widget'


def test_actual_missing_scroll_state_does_not_allocate_default_dict_or_change_dispatch():
    class NoDefault(dict):
        def get(self, key, *default):
            assert not default, 'Eager default object in movement path'
            return super().get(key)

    scroll = scroll_class()(123456)
    event = SimpleNamespace(ud=NoDefault())
    assert scroll.on_scroll_move(event) == 'BASE_SCROLL_MOVE'
    assert scroll.on_touch_move(event) == 'BASE_TOUCH_MOVE'
    assert scroll.on_scroll_stop(event) == 'BASE_SCROLL_STOP'
    assert scroll.cleared == 0


def test_actual_scroll_move_keeps_irreversible_slop_and_preview_boundary():
    scroll = scroll_class()(123456)
    intent = TouchIntent(0, 0, 8)
    state = {'mode': 'unknown', 'nte_intent': intent}
    event = SimpleNamespace(x=8, y=0, ud={scroll._get_uid(): state})
    assert scroll.on_scroll_move(event) is True
    assert state['mode'] == 'unknown' and scroll.cleared == 0
    event.x = 8.001
    assert scroll.on_scroll_move(event) == 'BASE_SCROLL_MOVE'
    assert state['mode'] == 'scroll' and scroll.cleared == 1
    event.x = 0
    assert scroll.on_scroll_move(event) == 'BASE_SCROLL_MOVE'
    assert state['mode'] == 'scroll'
