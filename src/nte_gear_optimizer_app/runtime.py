"""Process-local frozen Windows compatibility; no Kivy or system changes."""


def configure_frozen_paths(system, site):
    # kivy_deps.angle 0.5.0 iterates [sys.prefix, site.USER_BASE] and calls
    # os.path.join unconditionally. PyInstaller disables the user site and
    # sets USER_BASE=None. Supply the existing bundle root as a string;
    # do not enable the user site or edit installed third-party code.
    if (
        system.platform == 'win32'
        and getattr(system, 'frozen', False)
        and site.USER_BASE is None
    ):
        site.USER_BASE = system._MEIPASS
