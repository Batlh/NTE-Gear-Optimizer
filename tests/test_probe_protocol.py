import random
import string

import pytest

from nte_gear_optimizer_app.probe_protocol import encode_probe, decode_probe


def large_state():
    source = random.Random(42)
    return {
        'step': 3,
        'result': {
            str(i): ''.join(source.choices(string.ascii_letters, k=120))
            for i in range(300)
        },
    }


def test_small_and_large_real_state_roundtrip_below_android_line_limit():
    for state in [{'step': 0, 'name': 'Umlaute äöüß 🥝'}, large_state()]:
        lines = encode_probe(state, 123)
        assert all(len(line.encode('utf-8')) < 3000 for line in lines)
        logs = '\n'.join('11-27 14:00:00 I python: ' + line for line in lines)
        assert decode_probe(logs) == state


def test_partial_snapshot_does_not_mix_with_complete_previous_or_next():
    large = large_state()
    first = encode_probe({'step': 2}, 1)
    second = encode_probe(large, 2)
    assert len(second) > 1
    assert decode_probe('\n'.join(first + second[:-1])) == {'step': 2}
    with pytest.raises(AssertionError):
        decode_probe('\n'.join(second[:-1]))
    third = encode_probe({'step': 3, 'complete': True}, 3)
    assert decode_probe('\n'.join(first + second[:-1] + third)) == {
        'step': 3,
        'complete': True,
    }


def test_corruption_fails_instead_of_returning_stale_observation():
    lines = encode_probe(large_state(), 2)
    part = lines[-1]
    lines[-1] = part[:-1] + ('A' if part[-1] != 'A' else 'B')
    with pytest.raises(ValueError, match='checksum'):
        decode_probe('\n'.join(encode_probe({'step': 2}, 1) + lines))


def test_out_of_order_and_identical_repeat_are_safe_but_conflict_fails():
    state = large_state()
    lines = encode_probe(state, 123)
    assert decode_probe('\n'.join([lines[0]] + lines[::-1])) == state
    altered = lines[0][:-1] + ('A' if lines[0][-1] != 'A' else 'B')
    with pytest.raises(ValueError, match='Conflicting'):
        decode_probe('\n'.join([lines[0], altered] + lines[1:]))


def test_truncated_legacy_record_is_not_silently_accepted():
    with pytest.raises(Exception):
        decode_probe('NTE_CI_STATE=eJztnXFz')
