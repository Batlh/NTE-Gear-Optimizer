"""Native display policy. No global unthrottled idle render loop."""

import math


def frame_limit(display):
    value = display.get('native_max_hz') or display.get('active_hz')
    if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 1:
        return None
    return math.ceil(value)


def configure_frame_policy(config, platform):
    from .scroll_observer import display_refresh

    try:
        display = display_refresh(platform)
    except Exception as error:
        display = {
            'active_hz': None,
            'native_max_hz': None,
            'reason': type(error).__name__,
        }
    target = frame_limit(display)
    if target is not None:
        config.set('graphics', 'maxfps', str(target))
    config.set('graphics', 'vsync', '1')
    return {
        'display': display,
        'requested_maxfps': target,
        'vsync_requested': True,
        'idle': 'Canvas remains event-driven; no force-draw or maxfps=0 busy loop.',
        'status': 'REQUESTED' if target is not None else 'UNVERIFIED_REFRESH_READ',
    }


def request_android_mode(emit):
    from android.runnable import run_on_ui_thread
    from jnius import autoclass

    @run_on_ui_thread
    def apply():
        try:
            activity = autoclass('org.kivy.android.PythonActivity').mActivity
            display = activity.getWindowManager().getDefaultDisplay()
            current = display.getMode()
            modes = [
                m
                for m in display.getSupportedModes()
                if m.getPhysicalWidth() == current.getPhysicalWidth()
                and m.getPhysicalHeight() == current.getPhysicalHeight()
            ]
            selected = max(modes, key=lambda m: m.getRefreshRate())
            window = activity.getWindow()
            attributes = window.getAttributes()
            attributes.preferredDisplayModeId = selected.getModeId()
            attributes.preferredRefreshRate = selected.getRefreshRate()
            window.setAttributes(attributes)
            emit(
                'display_mode_requested',
                mode_id=selected.getModeId(),
                requested_hz=selected.getRefreshRate(),
                active_hz=display.getRefreshRate(),
            )
        except Exception as error:
            emit('display_mode_request_unverified', reason=type(error).__name__)

    apply()
