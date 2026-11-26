from configparser import ConfigParser
import pytest
from nte_gear_optimizer_app.input_config import configure_input


def config():
    instance = ConfigParser()
    instance.read_dict(
        {
            'input': {
                'mouse': 'mouse,multitouch_on_demand',
                'other': 'preserve-this-provider',
            }
        }
    )
    return instance


def test_android_removes_previously_persisted_duplicate_mouse_only():
    instance = config()
    configure_input(instance, 'android')
    assert not instance.has_option('input', 'mouse')
    assert instance.get('input', 'other') == 'preserve-this-provider'
    configure_input(instance, 'android')
    assert not instance.has_option('input', 'mouse')


@pytest.mark.parametrize('platform', ['win', 'linux', 'macosx'])
def test_desktop_mouse_is_preserved(platform):
    instance = config()
    configure_input(instance, platform)
    assert instance.get('input', 'mouse') == 'mouse,multitouch_on_demand'
    assert instance.get('input', 'other') == 'preserve-this-provider'
