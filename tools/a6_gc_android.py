"""Four-page CI-only real-touch profiling; no model or scroll setters."""

import json, subprocess, time, traceback, os
import a3_android_common as ui

out = ui.Path('build/a6_gc_android')
out.mkdir(parents=True, exist_ok=False)
blocks = []
baseline = os.environ.get('NTE_A5_BASELINE') == '1'
compare = os.environ.get('NTE_A5_COMPARE') == '1'
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
        for gc_mode in [
            'BASE',
            'FREEZE',
            'DEFER',
            'BOTH',
            'BOTH',
            'DEFER',
            'FREEZE',
            'BASE',
        ]:
            enabled = True
            ui.adb(
                'shell',
                'am',
                'start',
                '--activity-single-top',
                '-n',
                'io.github.batlh.nte_gear_optimizer/org.kivy.android.PythonActivity',
                '--es',
                'nte_ci_gc_mode',
                gc_mode,
            )
            time.sleep(0.8)
            s = ui.fresh()
            assert s['performance_probe']['gc_policy']['mode'] == gc_mode
            assert s['performance_probe']['gc_policy']['requested'] is None
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
                    from a6_check_attribution import check_attribution

                    check_attribution(f)
            blocks.append(
                {
                    'page': page,
                    'profiling': enabled,
                    'gc_mode': gc_mode,
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
    ui.adb(
        'shell',
        'am',
        'start',
        '--activity-single-top',
        '-n',
        'io.github.batlh.nte_gear_optimizer/org.kivy.android.PythonActivity',
        '--es',
        'nte_ci_gc_mode',
        'BOTH',
    )
    time.sleep(0.8)
    s = ui.fresh()
    assert s['performance_probe']['gc_policy']['mode'] == 'BOTH'
    memory_start_count = s['performance_probe']['gc_policy']['deferred_gestures']
    memory_samples = []
    import re

    for i in range(200):
        ui.swipe(s['page_scroll'], s, reverse=bool(i % 2))
        time.sleep(0.8)
        s = ui.fresh()
        if i in (19, 99, 199):
            raw = ui.adb(
                'shell', 'dumpsys', 'meminfo', 'io.github.batlh.nte_gear_optimizer'
            )
            if isinstance(raw, bytes):
                raw = raw.decode('utf-8')
            (out / f'memory_{i + 1}.txt').write_text(
                raw, encoding='utf-8', newline='\n'
            )
            match = re.search(r'TOTAL PSS:\s*(\d+)', raw)
            assert match, raw[-2000:]
            memory_samples.append(
                {
                    'gestures': i + 1,
                    'pss_kb': int(match.group(1)),
                    'gc': s['performance_probe']['gc_policy'],
                }
            )
    assert (
        s['performance_probe']['gc_policy']['deferred_gestures'] - memory_start_count
        >= 200
    )
    values = [v['pss_kb'] for v in memory_samples]
    assert values[-1] <= values[1] + max(8192, values[1] * 0.05), values

except Exception:
    failure = traceback.format_exc()
finally:
    result = {
        'status': 'MEASURED' if not failure else 'FAIL',
        'failure': failure,
        'profiling_blocks': blocks,
        'memory_samples': locals().get('memory_samples', []),
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
