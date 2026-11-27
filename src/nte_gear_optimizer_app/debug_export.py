"""User-triggered local report delivery; no networking or storage permissions."""

from pathlib import Path
import sys


def desktop_report(report, filename):
    directory = Path.home() / 'Downloads'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    with path.open('x', encoding='utf-8', newline='\n') as output:
        output.write(report)
    return str(path)


def android_share(report, filename):
    from jnius import autoclass, cast

    activity = autoclass('org.kivy.android.PythonActivity').mActivity
    directory = Path(str(activity.getCacheDir().getAbsolutePath())) / 'debug_reports'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    with path.open('x', encoding='utf-8', newline='\n') as output:
        output.write(report)
    uri = autoclass('androidx.core.content.FileProvider').getUriForFile(
        activity,
        str(activity.getPackageName()) + '.debugfiles',
        autoclass('java.io.File')(str(path)),
    )
    intent_type = autoclass('android.content.Intent')
    intent = intent_type(intent_type.ACTION_SEND)
    intent.setType('text/plain')
    intent.putExtra(intent_type.EXTRA_STREAM, cast('android.os.Parcelable', uri))
    intent.setClipData(
        autoclass('android.content.ClipData').newRawUri('NTE Debugbericht', uri)
    )
    intent.addFlags(intent_type.FLAG_GRANT_READ_URI_PERMISSION)
    # createChooser is overloaded. Pyjnius cannot resolve a Python str as
    # CharSequence here (confirmed on the emulator); provide the declared
    # Java interface explicitly instead of relying on implicit conversion.
    title = cast(
        'java.lang.CharSequence',
        autoclass('java.lang.String')('Debug-Bericht teilen oder speichern'),
    )
    activity.startActivity(intent_type.createChooser(intent, title))
    return filename


def android_download(report, filename):
    from jnius import autoclass

    if autoclass('android.os.Build$VERSION').SDK_INT < 29:
        raise RuntimeError(
            'Downloads ohne Speicherberechtigung ab Android 10; bitte Teilen verwenden.'
        )
    activity = autoclass('org.kivy.android.PythonActivity').mActivity
    values = autoclass('android.content.ContentValues')()
    # Strings also avoid ambiguous boxed Integer/Long JNI overloads.
    values.put('_display_name', filename)
    values.put('mime_type', 'text/plain')
    values.put('relative_path', 'Download/')
    values.put('is_pending', '1')
    resolver = activity.getContentResolver()
    collection = autoclass('android.provider.MediaStore$Downloads').EXTERNAL_CONTENT_URI
    uri = resolver.insert(collection, values)
    if uri is None:
        raise OSError('Downloads konnte nicht angelegt werden')
    stream = resolver.openOutputStream(uri, 'w')
    if stream is None:
        raise OSError('Downloads konnte nicht geöffnet werden')
    writer = autoclass('java.io.OutputStreamWriter')(stream, 'UTF-8')
    try:
        writer.write(report)
        writer.flush()
    finally:
        writer.close()
    values.clear()
    values.put('is_pending', '0')
    resolver.update(uri, values, None, None)
    return 'Downloads / ' + filename


def build_metadata():
    import json

    for path in [
        Path(getattr(sys, '_MEIPASS', '.')) / 'BUILD_METADATA.json',
        Path('BUILD_METADATA.json'),
    ]:
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except OSError, ValueError:
            continue
    return {'commit': 'development-unbundled'}
