"""Wait for actual native IME geometry; never retry or alter a tested touch."""

import json
import time


class NativeUI:
    def __init__(self, ui):
        self.ui = ui
        self.barriers = []

    def __getattr__(self, name):
        return getattr(self.ui, name)

    def adb(self, *args):
        result = self.ui.adb(*args)
        if args == ('shell', 'input', 'keyevent', '66'):
            self.wait_closed()
        return result

    def wait_closed(self):
        started = time.monotonic()
        previous = None
        stable = 0
        observations = []
        while time.monotonic() - started < 15:
            s = self.ui.fresh()
            ime = self.ui.read_ime_state(
                self.ui.adb('shell', 'dumpsys', 'input_method')
            )
            surface = s['native_surface']['screen_rect']
            frame = s['frame']
            geometry = (tuple(surface), tuple(frame), tuple(s['next']))
            closed = (
                ime['shown'] is False
                and not any(v['focus'] for v in s['inputs'].values())
                and abs(surface[1] - frame[1]) <= 2
                and abs(surface[1] + surface[3] - frame[3]) <= 2
            )
            observations.append(
                {
                    'native_ime': ime,
                    'surface': surface,
                    'frame': frame,
                    'next': s['next'],
                    'closed_and_restored': closed,
                }
            )
            stable = stable + 1 if closed and geometry == previous else 0
            previous = geometry
            if stable >= 1:
                self.barriers.append(
                    {
                        'seconds': time.monotonic() - started,
                        'observations': observations,
                    }
                )
                (self.ui.out / 'h01_keyboard_barriers.json').write_text(
                    json.dumps(self.barriers, indent=2) + '\n',
                    encoding='utf-8',
                    newline='\n',
                )
                return
        raise AssertionError(
            ('Native keyboard/coordinate geometry did not settle', observations)
        )
