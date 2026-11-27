import importlib.util
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'tools/a4_compare_logging.py'
spec = importlib.util.spec_from_file_location('a4_compare', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def blocks():
    return [
        {
            'logging': enabled,
            'seq_before': 1,
            'seq_after': 2 if enabled else 1,
            'gestures': [{'frame_interval_median_ms': 16.667}] * 4,
        }
        for enabled in [True, False, False, True]
    ]


def test_equal_block_intervals_meet_fixed_equivalence_band():
    result = module.compare(blocks())
    assert result['status'] == 'PASS_EQUIVALENT_WITHIN_2_PERCENT'
    assert result['bootstrap_95_percent_interval_change_percent'] == [0, 0]


def test_logging_off_must_be_proven_by_sequence_boundary():
    rows = blocks()
    rows[1]['seq_after'] = 3
    assert module.compare(rows)['status'] == 'FAIL_LOGGING_NOT_DISABLED'


def test_small_sample_is_not_silently_declared_equivalent():
    assert module.compare(blocks()[:2])['status'] == 'UNVERIFIED_TOO_FEW_ABBA_BLOCKS'


def test_slow_logging_is_not_a_pass():
    rows = blocks()
    for row in rows:
        if row['logging']:
            row['gestures'] = [{'frame_interval_median_ms': 30}] * 4
    assert module.compare(rows)['status'] == 'UNVERIFIED_NOISY_OR_OUTSIDE_EQUIVALENCE'
