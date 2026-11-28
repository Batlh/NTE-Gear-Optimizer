"""Skip diagnostic JNI polling only for a confirmed closed IME during scrolling.

This never controls focus/keyboard/viewport; those paths are unchanged. Unknown
or visible keyboard states and any focused field retain the existing polling.
Normal idle polling resumes as soon as the scrolling gesture settles.
"""


def should_poll(*, scrolling, focused, last_state):
    return not (
        scrolling
        and not focused
        and isinstance(last_state, dict)
        and last_state.get('ime_visible') is False
    )
