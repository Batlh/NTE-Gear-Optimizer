"""Read current manager and service WINDOW state, never Gboard's view flag."""

import re


def read_ime_state(dump):
    manager = dump.split('mStartInputHistory:', 1)[0]
    shown = re.findall(r'\bmInputShown=(true|false)\b', manager)
    sections = dump.split('Input method service state for ', 1)
    if len(shown) != 1 or len(sections) != 2:
        raise ValueError('Missing or ambiguous current IME manager/service state')
    visible = re.findall(r'\bmWindowVisible=(true|false)\b', sections[1])
    if len(visible) != 1 or visible[0] != shown[0]:
        raise ValueError('Missing, ambiguous or transitional IME window state')
    return {
        'shown': shown[0] == 'true',
        'manager_input_shown': shown[0],
        'service_window_visible': visible[0],
    }
