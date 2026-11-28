"""Actual CI waiting code must reject stale or still-moving observations."""

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def runner(states):
    source = (ROOT / 'tools/a6_catalog_android.py').read_text(encoding='utf-8')
    fn = next(
        n
        for n in ast.parse(source).body
        if isinstance(n, ast.FunctionDef) and n.name == 'fresh_idle_after_gesture'
    )
    calls = []
    reads = []
    tick = [0]

    def fresh():
        state = states[min(len(reads), len(states) - 1)]
        reads.append(state)
        return state

    def now():
        tick[0] += 1
        return tick[0]

    ns = {
        'ui': SimpleNamespace(adb=lambda *args: calls.append(args), fresh=fresh),
        'activity': 'test.activity',
        'uuid': SimpleNamespace(
            uuid4=lambda: SimpleNamespace(hex='after_this_gesture')
        ),
        'time': SimpleNamespace(monotonic=now),
    }
    exec(
        compile(
            ast.Module(body=[fn], type_ignores=[]),
            '<actual idle snapshot wait>',
            'exec',
        ),
        ns,
    )
    return ns['fresh_idle_after_gesture'], calls, reads


def state(nonce, scroll=False, contacts=0):
    return {
        'performance_probe': {
            'idle_snapshot_nonce': nonce,
            'scroll_active': scroll,
            'active_contacts': contacts,
        }
    }


def test_actual_wait_ignores_old_idle_and_new_but_moving_states():
    expected = state('after_this_gesture')
    fn, calls, reads = runner(
        [
            state('previous'),
            state('after_this_gesture', True),
            state('after_this_gesture', False, 1),
            expected,
        ]
    )
    assert fn() is expected and len(reads) == 4
    assert calls[0][-2:] == ('nte_ci_idle_snapshot_nonce', 'after_this_gesture')


def test_actual_wait_never_uses_a_stale_idle_snapshot_as_success():
    fn, calls, reads = runner([state('previous')])
    with pytest.raises(AssertionError, match='No new actual idle snapshot'):
        fn()
    assert len(reads) > 1 and calls
