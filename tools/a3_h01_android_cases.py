"""Actual adb MotionEvents on app controls with drift and 300/400ms duration."""

import time, json


def run(ui):
    records = []
    s = ui.fresh()
    policy = s['performance_probe']['touch_slop_policy']
    assert policy['source'] == 'Android ViewConfiguration.getScaledTouchSlop', policy
    assert policy['native_px'] > 0
    density = policy['density']

    def gesture(rect, s, drift, hold):
        x, y, w, h = ui.screen_rect(rect, s)
        scale = s['native_surface']['screen_rect'][2] / s['window'][0]
        a, b = round(x + w / 2), round(y + h / 2)
        ui.adb(
            'shell',
            'input',
            'swipe',
            str(a),
            str(b),
            str(a),
            str(round(b - drift * density * scale)),
            str(hold),
        )
        now = ui.fresh()
        records.append(
            {
                'requested_native_down': [a, b],
                'requested_native_up': [a, round(b - drift * density * scale)],
                'before_native_surface': s['native_surface'],
                'before_visible_frame': s['frame'],
                'after_native_surface': now['native_surface'],
                'drift_dp': drift,
                'requested_duration_ms': hold,
                'step': now['step'],
                'recent_intents': now['performance_probe']['touch_intents'][-2:],
            }
        )
        (ui.out / 'h01_touch_attempts.json').write_text(
            json.dumps(records, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
            newline='\n',
        )
        return now

    s = gesture(s['next'], s, 16, 400)
    assert s['step'] == 0, 'Swipe on footer Weiter navigated'
    for drift, hold in [(3, 300), (6, 400)]:
        s = gesture(s['next'], s, drift, hold)
        assert s['step'] == 1, ('Held Weiter lost', drift, hold)
        ui.tap(s['back'], s)
        s = ui.fresh()
        rect, s = ui.reach(
            lambda s: s['selectors']['Charakter']['rect'], lambda s: s['page_scroll']
        )
        s = gesture(rect, s, drift, hold)
        assert s['modal']['title'] == 'Charakter', ('Held selector lost', drift)
        ui.tap(s['modal']['cancel'], s)
        s = ui.fresh()
        s = gesture(s['debug_button'], s, drift, hold)
        assert s.get('debug', {}).get('buttons'), ('Held Debug lost', drift)
        ui.tap(s['debug']['buttons']['Schließen'], s)
        s = ui.fresh()
        rect, s = ui.reach(
            lambda s: s['inputs']['level:ArkLevel']['rect'], lambda s: s['page_scroll']
        )
        s = gesture(rect, s, drift, hold)
        assert s['inputs']['level:ArkLevel']['focus'], ('Held field not focused', drift)
        ui.adb('shell', 'input', 'keyevent', '66')
        s = ui.fresh()
    rect, s = ui.reach(
        lambda s: s['selectors']['Charakter']['rect'], lambda s: s['page_scroll']
    )
    before = s['scroll_y']
    s = gesture(rect, s, 32, 400)
    assert not s.get('modal'), 'Swipe opened selection'
    assert abs(s['scroll_y'] - before) > 0.001, 'Swipe did not scroll'
    rect, s = ui.reach(
        lambda s: s['inputs']['level:ArkLevel']['rect'], lambda s: s['page_scroll']
    )
    s = gesture(rect, s, 16, 400)
    assert not s['inputs']['level:ArkLevel']['focus'], 'Swipe focused field'
    # The default UNKNOWN profile has no relevant zero group. Prepare an
    # actual supported DAMAGE/ANG fixture through real selectors first.
    ui.choose('Leistungstyp', 'DAMAGE')
    ui.choose('Skalierung', 'ANG')
    s = ui.fresh()
    ui.tap(s['next'], s)
    s = ui.fresh()
    for drift, hold in [(3, 300), (6, 400)]:
        rect, s = ui.reach(lambda s: s['zeros'][0], lambda s: s['page_scroll'])
        s = gesture(rect, s, drift, hold)
        assert any(
            v['text'] == '0' for k, v in s['inputs'].items() if k.startswith('current:')
        ), 'Held zero did not fill fields'
    time.sleep(3.2)  # bounded async writer flush, never force a model action
    directory = 'files/nte_debug/logs'
    names = ui.adb(
        'shell', 'run-as', 'io.github.batlh.nte_gear_optimizer', 'ls', directory
    ).splitlines()
    events = []
    for name in names:
        if name.startswith('events_') and name.endswith('.jsonl'):
            raw = ui.adb(
                'shell',
                'run-as',
                'io.github.batlh.nte_gear_optimizer',
                'cat',
                directory + '/' + name,
            )
            events.extend(json.loads(line) for line in raw.splitlines() if line.strip())
    zero_events = [e for e in events if e['event'] == 'zero_bonus']
    assert len(zero_events) >= 2, 'Both held zero actions must actually execute'
    ui.tap(s['back'], s)
    s = ui.fresh()
    assert s['step'] == 0
    report = {
        'status': 'PASS',
        'policy': policy,
        'actual_motion_cases': records,
        'actual_zero_events': zero_events,
    }
    (ui.out / 'h01_touch_intent.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
        newline='\n',
    )
