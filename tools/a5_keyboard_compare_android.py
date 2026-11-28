"""Four-page CI-only real-touch profiling; no model or scroll setters."""

import json, subprocess, time, traceback, os
import a3_android_common as ui

out = ui.Path('build/a5_keyboard_compare_android')
out.mkdir(parents=True, exist_ok=False)
blocks = []
baseline = os.environ.get('NTE_A5_BASELINE') == '1'
compare = os.environ.get('NTE_A5_COMPARE') == '1'
replication = os.environ.get('NTE_A5_POLL_REPLICATION') == '1'
orders = [False, True, True, False] + (
    [True, False, False, True] if replication else []
)
failure = None
try:
    probe = json.loads(ui.Path('build/a3_probe_apk.json').read_text(encoding='utf-8'))
    ui.adb('install', '-r', probe['apk'])
    ui.adb('logcat', '-c')
    ui.adb(
        'shell',
        'am',
        'start',
        '-n',
        'io.github.batlh.nte_gear_optimizer/org.kivy.android.PythonActivity',
        '--ez',
        'nte_ci_test',
        'true',
        '--ez',
        'nte_a3_cause',
        'true',
    )
    for _ in range(45):
        time.sleep(1)
        try:
            s = ui.state()
            break
        except AssertionError:
            pass
    else:
        raise AssertionError('No native snapshot')
    ui.choose('Leistungstyp', 'DAMAGE')
    ui.choose('Skalierung', 'ANG')
    for page in range(4):
        s = ui.fresh()
        assert s['step'] == page
        assert (
            baseline
            or s['performance_probe']['display_listener_status'] == 'REGISTERED'
        ), s['performance_probe']
        for skip in orders:
            enabled = True
            ui.adb(
                'shell',
                'am',
                'start',
                '--activity-single-top',
                '-n',
                'io.github.batlh.nte_gear_optimizer/org.kivy.android.PythonActivity',
                '--ez',
                'nte_ci_keyboard_scroll_skip',
                str(skip).lower(),
            )
            s = ui.fresh()
            assert baseline or s['performance_probe']['profiling_enabled'] is enabled
            assert s['performance_probe']['keyboard_scroll_skip'] is skip
            before_skips = s['performance_probe']['keyboard_probe_skips']
            before = s['performance_probe'].get('refresh_reads')
            old = {g['touch_id'] for g in s['performance_probe']['gestures']}
            for reverse in [False, True]:
                ui.swipe(s['page_scroll'], s, reverse=reverse)
                time.sleep(1.6)
                s = ui.fresh()
            time.sleep(0.6)
            s = ui.fresh()
            p = s['performance_probe']
            assert baseline or p['refresh_reads_during_gesture'] == 0
            assert (
                (p['keyboard_probe_skips'] > before_skips)
                if skip
                else (p['keyboard_probe_skips'] == before_skips)
            ), (page, skip, before_skips, p['keyboard_probe_skips'])
            # No native display notifications expected on this fixed AVD.
            assert baseline or p['refresh_reads'] == before, (
                before,
                p.get('refresh_reads'),
            )
            gestures = [g for g in p['gestures'] if g['touch_id'] not in old]
            moving = [
                g for g in gestures if g.get('status') == 'MEASURED_GL_FLIP_PROXY'
            ]
            assert moving, ('No actual scrolling', page, gestures)
            for g in moving:
                assert (
                    baseline
                    or g['first_movement_startpoint'] == 'SYSTEM_TOUCH_SLOP_CROSSED'
                )
                if enabled:
                    f = g['frame_profile']
                    assert f['frames_observed'] > 0
                    assert len(f['rows']) == f['rows_retained'] > 0
                    assert f['hook_status'] == 'ACTUAL_WINDOW_FLIP_CALL', f
                    assert f['inventory']['page'] == page + 1, f
            blocks.append(
                {
                    'page': page,
                    'profiling': enabled,
                    'keyboard_scroll_skip': skip,
                    'skips_before': before_skips,
                    'skips_after': p['keyboard_probe_skips'],
                    'refresh_reads': before,
                    'gestures': gestures,
                }
            )
        (out / f'page_{page}.png').write_bytes(
            subprocess.check_output(['adb', 'exec-out', 'screencap', '-p'])
        )
        if page < 3:
            ui.tap(s['next'], s)
            time.sleep(1)
except Exception:
    failure = traceback.format_exc()
finally:
    result = {
        'status': 'MEASURED' if not failure else 'FAIL',
        'failure': failure,
        'replication': replication,
        'order': orders,
        'profiling_blocks': blocks,
        'apk_probe': locals().get('probe'),
        'scope': 'AVD GL flip proxy; CPU inclusive spans; not Samsung physical timing.',
    }
    (out / 'result.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
        newline='\n',
    )
    (out / 'app_logcat.txt').write_text(ui.app_logs(), encoding='utf-8', newline='\n')
    ui.collect_private_debug()
assert not failure, failure
