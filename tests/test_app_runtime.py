from types import SimpleNamespace
from nte_gear_optimizer_app.runtime import configure_frozen_paths


def test_frozen_windows_angle_path_without_enabling_user_site():
    system = SimpleNamespace(platform='win32', frozen=True, _MEIPASS='bundle')
    site = SimpleNamespace(USER_BASE=None, ENABLE_USER_SITE=False)
    configure_frozen_paths(system, site)
    assert site.USER_BASE == 'bundle' and site.ENABLE_USER_SITE is False


def test_existing_user_base_is_preserved():
    site = SimpleNamespace(USER_BASE='existing')
    configure_frozen_paths(
        SimpleNamespace(platform='win32', frozen=True, _MEIPASS='bundle'), site
    )
    assert site.USER_BASE == 'existing'


def test_source_python_and_other_platforms_are_not_changed():
    for system in (
        SimpleNamespace(platform='win32'),
        SimpleNamespace(platform='linux', frozen=True),
    ):
        site = SimpleNamespace(USER_BASE=None)
        configure_frozen_paths(system, site)
        assert site.USER_BASE is None
