"""Preflight the pinned p4a SDL manifest, before expensive native compilation."""

from configparser import ConfigParser
import hashlib
import json
from pathlib import Path
import shlex
from types import SimpleNamespace
import urllib.request
import xml.etree.ElementTree as ET

TEMPLATE_URL = 'https://raw.githubusercontent.com/kivy/python-for-android/9562d1b4f306d0af1e76991c711114010dea4152/pythonforandroid/bootstraps/_sdl_common/build/templates/AndroidManifest.tmpl.xml'
TEMPLATE_SHA = 'F87B043C6121E6C23796F6392FCFEA44A252630199ACF3989658E0F89ACF24D7'
ANDROID = '{http://schemas.android.com/apk/res/android}'


def provider_argument(config):
    app = config['app']
    assert '<' not in app.get('android.extra_manifest_application_arguments', ''), (
        'Application attribute option must not contain child XML'
    )
    args = shlex.split(app.get('p4a.extra_args', ''))
    values = [
        a.split('=', 1)[1]
        for a in args
        if a.startswith('--extra-manifest-application-xml=')
    ]
    assert len(values) == 1, 'Exactly one application-child XML argument required'
    provider = ET.fromstring(values[0])
    assert provider.tag == 'provider'
    assert (
        provider.attrib[ANDROID + 'name']
        == 'io.github.batlh.nte_gear_optimizer.DebugFileProvider'
    )
    assert (
        provider.attrib[ANDROID + 'authorities']
        == 'io.github.batlh.nte_gear_optimizer.debugfiles'
    )
    assert provider.attrib[ANDROID + 'exported'] == 'false'
    assert provider.attrib[ANDROID + 'grantUriPermissions'] == 'true'
    return values[0]


def preflight(root, output, template=None):
    from jinja2 import Environment, StrictUndefined

    config = ConfigParser()
    config.read(root / 'buildozer.spec', encoding='utf-8')
    child_xml = provider_argument(config)
    source_xml = (root / 'android/debug_provider.xml').read_text(encoding='utf-8')
    assert ET.tostring(ET.fromstring(child_xml)) == ET.tostring(
        ET.fromstring(' '.join(source_xml.splitlines()))
    )
    if template is None:
        template = urllib.request.urlopen(TEMPLATE_URL, timeout=30).read()
    assert hashlib.sha256(template).hexdigest().upper() == TEMPLATE_SHA
    text = template.decode('utf-8')
    app = config['app']
    args = SimpleNamespace(
        numeric_version=app.get('android.numeric_version', '1000001'),
        version=app['version'],
        min_sdk_version=int(app['android.minapi']),
        permissions=[],
        wakelock=False,
        billing_pubkey=None,
        extra_manifest_xml='',
        extra_manifest_application_arguments='',
        extra_manifest_application_xml=child_xml,
        allow_backup='true'
        if config.getboolean('app', 'android.allow_backup', fallback=True)
        else 'false',
        backup_rules='',
        android_apptheme='@android:style/Theme.NoTitleBar',
        window=not config.getboolean('app', 'fullscreen'),
        android_used_libs=[],
        meta_data=[],
        android_entrypoint='org.kivy.android.PythonActivity',
        manifest_orientation=app['orientation'],
        activity_launch_mode='',
        launcher=False,
        home_app=False,
        intent_filters='',
        service_class_name='org.kivy.android.PythonService',
        add_activity=[],
        package='io.github.batlh.nte_gear_optimizer',
    )
    output.mkdir(parents=True, exist_ok=False)
    results = []
    for debug in (True, False):
        rendered = (
            Environment(undefined=StrictUndefined)
            .from_string(text)
            .render(
                args=args,
                debug=debug,
                android_api=int(app['android.api']),
                service=False,
                service_data=[],
                native_services=[],
                url_scheme='',
            )
        )
        document = ET.fromstring(rendered)
        assert len(document.findall('./application/provider')) == 1
        assert not document.findall('./provider')
        assert document.find('./application').attrib[ANDROID + 'allowBackup'] == 'false'
        path = output / ('manifest_debug.xml' if debug else 'manifest_non_debug.xml')
        path.write_text(rendered, encoding='utf-8', newline='\n')
        results.append(
            {
                'debug': debug,
                'xml': 'PASS',
                'provider_location': 'application child',
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest().upper(),
            }
        )
    (output / 'result.json').write_text(
        json.dumps(
            {
                'status': 'PASS',
                'template_url': TEMPLATE_URL,
                'template_sha256': TEMPLATE_SHA,
                'cases': results,
            },
            indent=2,
        ),
        encoding='utf-8',
        newline='\n',
    )
    return results


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    print(preflight(root, root / 'build/manifest_preflight'))
