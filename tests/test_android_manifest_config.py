from configparser import ConfigParser
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from check_android_manifest import provider_argument


def config():
    value = ConfigParser()
    value.read(Path(__file__).resolve().parents[1] / 'buildozer.spec', encoding='utf-8')
    return value


def test_real_spec_provider_uses_child_xml_argument():
    assert '<provider ' in provider_argument(config())


def test_wrong_attribute_injection_is_rejected_before_compile():
    value = config()
    value['app']['android.extra_manifest_application_arguments'] = '<provider />'
    with pytest.raises(AssertionError, match='attribute option'):
        provider_argument(value)
