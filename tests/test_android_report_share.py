import sys
from pathlib import Path
from types import SimpleNamespace

from nte_gear_optimizer_app.debug_export import android_share


def test_chooser_uses_explicit_java_charsequence_and_read_only_content_uri(
    tmp_path, monkeypatch
):
    calls = []

    class JavaString:
        def __init__(self, text):
            self.text = text

    class CharSequence:
        def __init__(self, value):
            self.value = value

    class Activity:
        def getCacheDir(self):
            return SimpleNamespace(getAbsolutePath=lambda: str(tmp_path))

        def getPackageName(self):
            return 'io.github.batlh.nte_gear_optimizer'

        def startActivity(self, intent):
            calls.append(('start', intent))

    activity = Activity()

    class Intent:
        ACTION_SEND = 'send'
        EXTRA_STREAM = 'stream'
        FLAG_GRANT_READ_URI_PERMISSION = 1

        def __init__(self, action):
            self.action = action
            self.flags = []

        def setType(self, value):
            self.type = value

        def putExtra(self, key, value):
            self.stream = value

        def setClipData(self, value):
            self.clip = value

        def addFlags(self, value):
            self.flags.append(value)

        @staticmethod
        def createChooser(intent, title):
            assert isinstance(title, CharSequence), (
                'JNI overloaded method requires explicit CharSequence'
            )
            assert title.value.text == 'Debug-Bericht teilen oder speichern'
            return ('chooser', intent, title)

    def uri(context, authority, file):
        assert context is activity
        assert authority == 'io.github.batlh.nte_gear_optimizer.debugfiles'
        assert Path(file).parent == tmp_path / 'debug_reports'
        return 'content://' + authority + '/debug_reports/report.txt'

    classes = {
        'org.kivy.android.PythonActivity': SimpleNamespace(mActivity=activity),
        'androidx.core.content.FileProvider': SimpleNamespace(getUriForFile=uri),
        'java.io.File': lambda name: name,
        'android.content.Intent': Intent,
        'android.content.ClipData': SimpleNamespace(
            newRawUri=lambda name, uri: ('clip', name, uri)
        ),
        'java.lang.String': JavaString,
    }

    def cast(name, value):
        if name == 'java.lang.CharSequence':
            return CharSequence(value)
        assert name == 'android.os.Parcelable'
        return value

    monkeypatch.setitem(
        sys.modules,
        'jnius',
        SimpleNamespace(autoclass=lambda name: classes[name], cast=cast),
    )
    text = 'Umlaute äöüß – 🥝'
    assert android_share(text, 'report.txt') == 'report.txt'
    assert (tmp_path / 'debug_reports/report.txt').read_text(encoding='utf-8') == text
    assert len(calls) == 1
    intent = calls[0][1][1]
    assert intent.action == 'send' and intent.type == 'text/plain'
    assert intent.flags == [1]
    assert intent.stream.startswith('content://') and intent.clip[2] == intent.stream
