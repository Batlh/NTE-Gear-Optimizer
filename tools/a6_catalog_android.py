"""Actual AVD gestures: sourced normal catalog versus isolated presentation load."""

import json
import subprocess
import time
import traceback
import uuid

import a3_android_common as ui

out = ui.Path('build/a6_catalog_android')
out.mkdir(parents=True, exist_ok=False)
activity = 'io.github.batlh.nte_gear_optimizer/org.kivy.android.PythonActivity'
records = []
failure = None


def command(*args):
    ui.adb('shell', 'am', 'start', '--activity-single-top', '-n', activity, *args)
    return ui.fresh()


def compact_gesture(g):
    result = {k: v for k, v in g.items() if k != 'frame_profile'}
    p = g.get('frame_profile', {})
    result['frame_profile'] = {k: v for k, v in p.items() if k != 'rows'}
    return result


def physical_scroll(rect, s, reverse=False):
    x, y, w, h = ui.viewport(rect, s)
    start, end = (0.25, 0.80) if reverse else (0.80, 0.25)
    ui.adb(
        'shell',
        'input',
        'swipe',
        str(round(x + w / 2)),
        str(round(y + h * start)),
        str(round(x + w / 2)),
        str(round(y + h * end)),
        '900',  # Short AVD injections can coalesce; use proven real gesture duration.
    )


def fresh_idle_after_gesture():
    # Request a NEW snapshot after OS input returns. Old pre-gesture snapshots
    # are not idle evidence while serialization is deferred during inertia.
    nonce = uuid.uuid4().hex
    ui.adb(
        'shell',
        'am',
        'start',
        '--activity-single-top',
        '-n',
        activity,
        '--es',
        'nte_ci_idle_snapshot_nonce',
        nonce,
    )
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        s = ui.fresh()
        p = s['performance_probe']
        if (
            p.get('idle_snapshot_nonce') == nonce
            and not p['scroll_active']
            and p['active_contacts'] == 0
        ):
            return s
    raise AssertionError('No new actual idle snapshot after native gesture')


def list_to_last(s, expected_count, kind):
    modal = s['modal']
    expected = modal['rows'][-1]['id']
    assert len(modal['rows']) == expected_count, (kind, len(modal['rows']))
    seen_views = set()
    profiles = {}
    max_attached = 0
    # Actual swipes, never ScrollView.scroll_y mutation. The probe reports
    # NULL for virtual rows and real geometry only for attached recycled views.
    for iteration in range(180):
        modal = s['modal']
        rendered = [r for r in modal['rows'] if r['rect'] is not None]
        max_attached = max(max_attached, len(rendered))
        seen_views.update(r['view_uid'] for r in rendered)
        row = modal['rows'][-1]
        if row['rect'] is not None and ui.visible(row['rect'], modal['scroll'], s):
            time.sleep(1)
            s = ui.fresh()
            row = s['modal']['rows'][-1]
            if (
                row['rect'] is not None
                and ui.visible(row['rect'], s['modal']['scroll'], s)
                and not s['modal']['touch_active']
            ):
                break
        physical_scroll(modal['scroll'], s)
        s = fresh_idle_after_gesture()
        for g in s['performance_probe']['gestures']:
            if g.get('status') == 'MEASURED_GL_FLIP_PROXY' and str(
                g.get('scroll', '')
            ).startswith('selector:'):
                profiles[g['touch_id']] = compact_gesture(g)
    else:
        raise AssertionError(('Last entry not reachable', kind))
    assert max_attached < min(expected_count, 40), (
        kind,
        'Too many attached option widgets',
        max_attached,
    )
    assert len(seen_views) < min(expected_count, 60), (
        kind,
        'Views not reused',
        len(seen_views),
    )
    assert profiles, (kind, 'No measured scrolling')
    (out / (kind + '_last.png')).write_bytes(
        subprocess.check_output(['adb', 'exec-out', 'screencap', '-p'])
    )
    # Reacquire after screenshot transport, never tap a stale recycled position.
    s = ui.fresh()
    row = s['modal']['rows'][-1]
    assert (
        row['id'] == expected
        and row['rect'] is not None
        and ui.visible(row['rect'], s['modal']['scroll'], s)
    )
    ui.tap(row['rect'], s)
    s = ui.fresh()
    assert not s.get('modal')
    if kind == 'normal_arks':
        assert s['selectors']['Ark']['selected'] == expected
    else:
        assert s['load_mode']['choice'] == expected
    records.append(
        {
            'kind': kind,
            'entries': expected_count,
            'selected': expected,
            'max_attached_rows': max_attached,
            'unique_view_widgets': len(seen_views),
            'measured_gestures': list(profiles.values()),
        }
    )
    return s


try:
    ui.adb('shell', 'am', 'force-stop', 'io.github.batlh.nte_gear_optimizer')
    ui.adb('logcat', '-c')
    ui.adb(
        'shell',
        'am',
        'start',
        '-n',
        activity,
        '--ez',
        'nte_ci_test',
        'true',
        '--ez',
        'nte_a3_cause',
        'true',
    )
    for _ in range(40):
        time.sleep(1)
        try:
            s = ui.state()
            break
        except AssertionError:
            pass
    else:
        raise AssertionError('App did not start')
    assert s['load_mode']['available'] and not s['load_mode']['enabled']
    command('--ez', 'nte_ci_frame_profiling', 'true')
    rect, s = ui.reach(
        lambda s: s['selectors']['Ark']['rect'], lambda s: s['page_scroll']
    )
    ui.tap(rect, s)
    s = ui.fresh()
    assert all('Typ:' in r['name'] for r in s['modal']['rows'] if r['id'] is not None)
    s = list_to_last(s, 52, 'normal_arks')  # 51 sourced Arks + explicit no-choice
    old_state = s['comparison_inputs']
    for kind, count in [('arks', 300), ('inventory', 100)]:
        s = command('--es', 'nte_ci_load_list', kind)
        s = list_to_last(s, count, 'load_' + kind)
        assert s['comparison_inputs'] == old_state, (
            'Synthetic list mutated actual inputs'
        )
    for title, value in [
        ('Leistungstyp', 'DAMAGE'),
        ('Skalierung', 'ANG'),
        ('Krit möglich?', 'TRUE'),
        ('Bruch relevant?', 'TRUE'),
        ('Zyklusreaktion', 'NONE'),
    ]:
        ui.choose(title, value)
    s = ui.fresh()
    ui.tap(s['next'], s)
    s = ui.fresh()
    ui.tap(s['next'], s)
    s = ui.fresh()
    assert s['step'] == 2
    original = s['comparison_inputs']
    input_count = len(s['inputs'])
    for enabled in [False, True, True, False]:
        s = command('--ez', 'nte_ci_load_mode', 'true' if enabled else 'false')
        assert s['load_mode']['enabled'] == enabled
        assert s['comparison_inputs'] == original and len(s['inputs']) == input_count
        if enabled:
            assert (
                s['load_mode']['fields']
                == 4 * (input_count - ('white:WhitePanelBase' in s['inputs'])) // 2
            )
        old = {g['touch_id'] for g in s['performance_probe']['gestures']}
        for reverse in [False, True]:
            physical_scroll(s['page_scroll'], s, reverse=reverse)
            s = fresh_idle_after_gesture()
        gestures = [
            compact_gesture(g)
            for g in s['performance_probe']['gestures']
            if g['touch_id'] not in old and g.get('status') == 'MEASURED_GL_FLIP_PROXY'
        ]
        assert gestures, ('No actual step3 scrolling', enabled)
        inventories = [g['frame_profile']['inventory'] for g in gestures]
        assert all(
            i.get('page') == 3 and i.get('widgets', 0) > 0 for i in inventories
        ), inventories
        if enabled:
            assert all(350 <= i['widgets'] <= 550 for i in inventories), (
                'Load should be about400 actual widgets',
                inventories,
            )

        records.append(
            {
                'kind': 'load_step3' if enabled else 'normal_step3',
                'mode': enabled,
                'actual_inputs_unchanged': True,
                'active_load_fields': s['load_mode']['fields'] if enabled else 0,
                'gestures': gestures,
            }
        )
    assert s['comparison_inputs'] == original
    s = command('--ez', 'nte_ci_load_mode', 'true')
    key = '0:before:ScaleDirect'
    rect, s = ui.reach(
        lambda s: s['load_inputs'][key]['rect'], lambda s: s['page_scroll']
    )
    ui.tap(rect, s)
    ui.adb('shell', 'input', 'text', '1')
    s = ui.fresh()
    ui.tap(s['load_decimal_buttons'][key], s)
    ui.adb('shell', 'input', 'text', '5')
    s = ui.fresh()
    assert s['load_inputs'][key]['text'] == '1,5' and s['comparison_inputs'] == original
    (out / 'load_comma.png').write_bytes(
        subprocess.check_output(['adb', 'exec-out', 'screencap', '-p'])
    )
    ui.adb('shell', 'input', 'keyevent', '66')
    records.append(
        {'kind': 'load_numeric_input', 'value': '1,5', 'actual_inputs_unchanged': True}
    )
except Exception:
    failure = traceback.format_exc()
finally:
    (out / 'result.json').write_text(
        json.dumps(
            {
                'status': 'MEASURED' if failure is None else 'FAIL',
                'failure': failure,
                'records': records,
                'scope': 'AVD GL-flip proxy only; Samsung targets remain UNVERIFIED',
            },
            ensure_ascii=False,
            indent=2,
        )
        + '\n',
        encoding='utf-8',
        newline='\n',
    )
    (out / 'app_logcat.txt').write_text(ui.app_logs(), encoding='utf-8', newline='\n')
assert failure is None, failure
