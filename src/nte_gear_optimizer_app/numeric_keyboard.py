"""Explicit Android EditorInfo flags; no parsing or global Window changes."""

INTEGER_FLAGS = 2  # InputType.TYPE_CLASS_NUMBER
DECIMAL_SIGNED_FLAGS = 2 | 4096 | 8192


def flags_for(widget):
    return (
        INTEGER_FLAGS
        if getattr(widget, '_nte_integer_only', False)
        else DECIMAL_SIGNED_FLAGS
    )


class NumericKeyboard:
    """Apply only on native keyboard creation or an actual flag change."""

    def __init__(self, apply, emit):
        self.apply = apply
        self.emit = emit
        self.last = None

    def configure(self, widget, new_keyboard):
        flags = flags_for(widget)
        if new_keyboard or flags != self.last:
            self.apply(flags)
            self.last = flags
            self.emit('numeric_keyboard_flags_requested', flags=flags)


def android_keyboard(emit):
    from android.runnable import run_on_ui_thread
    from jnius import autoclass

    activity = autoclass('org.kivy.android.PythonActivity')

    @run_on_ui_thread
    def apply(flags):
        try:
            # Pinned p4a SDL2 PythonActivity changes InputType and restarts
            # the existing editor; no hide/show or keyboard ownership change.
            activity.changeKeyboard(flags)
            emit('numeric_keyboard_flags_applied', flags=flags)
        except Exception as error:
            from .debug_journal import private_traceback

            emit('numeric_keyboard_flags_failed', error=private_traceback(error))

    return NumericKeyboard(apply, emit)
