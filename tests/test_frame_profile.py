from nte_gear_optimizer_app.frame_profile import FrameProfiler
from types import SimpleNamespace


def test_buffer_is_bounded_and_has_cpu_spans_not_exclusive_sum():
    now = [0.0]

    def actual_flip():
        now[0] += 0.0002

    window = SimpleNamespace(
        bind=lambda **kw: None, unbind=lambda **kw: None, flip=actual_flip
    )
    p = FrameProfiler(window, lambda: True, lambda: now[0])
    p.begin()
    for _ in range(1300):
        p.add('layout', 0.1)
        p.add('keyboard_probe', 2)
        now[0] += 0.008
        p.before_draw()
        now[0] += 0.001
        p.before_flip()
        window.flip()
    v = p.finish()
    assert (
        v['frames_observed'] == 1300 and len(v['rows']) == 1200 and v['raw_truncated']
    )
    assert v['statistics']['keyboard_probe_ms']['median'] == 2
    assert v['statistics']['layout_calls']['median'] == 1
    assert 'Inclusive/nested' in v['scope']
    assert p.finish()['rows'] == []
    p.stop()


def test_disabled_profile_does_not_record_or_force_frames():
    p = FrameProfiler(None, lambda: True)
    p.enabled = False
    assert not p.recording()
    p.before_draw()
    p.before_flip()
    assert p.finish()['frames_observed'] == 0
    p.stop()
