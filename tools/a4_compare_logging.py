"""Read-only ABBA comparison, fixed equivalence band, no fabricated PASS."""

import random, statistics


def compare(blocks, iterations=4000):
    modes = {True: [], False: []}
    for block in blocks:
        if not block['logging'] and block['seq_before'] != block['seq_after']:
            return {'status': 'FAIL_LOGGING_NOT_DISABLED'}
        values = [
            g['frame_interval_median_ms']
            for g in block['gestures']
            if g.get('frame_interval_median_ms') is not None
        ]
        if values:
            modes[block['logging']].append(statistics.median(values))
    if any(len(values) < 2 for values in modes.values()):
        return {
            'status': 'UNVERIFIED_TOO_FEW_ABBA_BLOCKS',
            'block_counts': {str(k): len(v) for k, v in modes.items()},
        }
    rng = random.Random(204)
    samples = []
    for _ in range(iterations):
        on = statistics.median(rng.choices(modes[True], k=len(modes[True])))
        off = statistics.median(rng.choices(modes[False], k=len(modes[False])))
        if off <= 0:
            return {'status': 'FAIL_INVALID_FRAME_INTERVAL'}
        samples.append(100 * (on / off - 1))
    samples.sort()
    lo, hi = (
        samples[int(0.025 * iterations)],
        samples[min(iterations - 1, int(0.975 * iterations))],
    )
    status = (
        'PASS_EQUIVALENT_WITHIN_2_PERCENT'
        if lo >= -2 and hi <= 2
        else 'UNVERIFIED_NOISY_OR_OUTSIDE_EQUIVALENCE'
    )
    return {
        'status': status,
        'median_block_frame_interval_ms': {
            str(k): statistics.median(v) for k, v in modes.items()
        },
        'bootstrap_95_percent_interval_change_percent': [round(lo, 3), round(hi, 3)],
        'equivalence_band_percent': [-2, 2],
        'bootstrap_unit': 'ABBA block (not individual correlated frames)',
        'scope': 'Virtual-runner descriptive comparison, not Samsung-device proof.',
    }


if __name__ == '__main__':
    blocks = [
        {
            'logging': enabled,
            'seq_before': 1,
            'seq_after': 2 if enabled else 1,
            'gestures': [{'frame_interval_median_ms': 16.667}] * 4,
        }
        for enabled in [True, False, False, True]
    ]
    assert compare(blocks)['status'] == 'PASS_EQUIVALENT_WITHIN_2_PERCENT'
    blocks[1]['seq_after'] = 3
    assert compare(blocks)['status'] == 'FAIL_LOGGING_NOT_DISABLED'
    print('Comparison self-check: fixed equivalence band and logging-off guard PASS')
