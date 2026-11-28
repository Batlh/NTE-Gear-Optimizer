"""Assertions against the actual native/desktop frame profile, not a fake engine."""


def check_attribution(profile):
    a = profile['attribution']
    assert a['runtime_hooks'] == 'INSTALLED_CLOCK_INPUT_GC_CORELABEL', a
    if a['schema'] >= 2:
        assert a['clock_idle_hook'] and a['input_poll_hook']
    frames = a['frames']
    assert len(frames) == profile['rows_retained'] > 0
    assert any(f['clock_calls'] > 0 for f in frames), (
        'No actual Clock callback observed'
    )
    assert all(f['overflow'] == 0 for f in frames), 'Incomplete attribution'
    assert len(a['callback_names']) <= 128
    for raw, f in zip(profile['rows'], frames):
        assert len(f['clock_top5']) <= 5
        for i, calls, ms in f['clock_top5']:
            assert 0 <= i < len(a['callback_names']) and calls > 0 and ms >= 0
        if raw[1] is not None:
            accounted = sum(f['exclusive_ms']) + f['unassigned_ms']
            assert abs(accounted - raw[1]) <= 0.002, (accounted, raw[1])
    # Actual input-event count is retained even when multiple events occur per
    # flip; inertia-only frames legitimately contain zero events.
    assert sum(f['input_calls'] for f in frames) > 0, 'No real move dispatch measured'
    return {
        'status': 'PASS',
        'frames': len(frames),
        'input_events': sum(f['input_calls'] for f in frames),
        'clock_callbacks': sum(f['clock_calls'] for f in frames),
        'gc_collections': sum(sum(f['gc_counts']) for f in frames),
        'texture_changes': sum(f['texture_changes'] for f in frames),
    }
