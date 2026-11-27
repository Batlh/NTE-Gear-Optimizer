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


def android_share_context():
    """Resolve APK classes on the existing app thread before worker handoff.

    A newly attached native worker cannot FindClass the AndroidX provider
    through Android's bootstrap class loader. Keep the loaded class reference;
    report/file creation and provider URI work still run in the worker.
    """
    from jnius import autoclass

    return {
        'activity': autoclass('org.kivy.android.PythonActivity').mActivity,
        'provider': autoclass('androidx.core.content.FileProvider'),
    }


def android_share(report, filename, *, context=None):
    from jnius import autoclass, cast

    context = context if context is not None else android_share_context()
    activity = context['activity']
    directory = Path(str(activity.getCacheDir().getAbsolutePath())) / 'debug_reports'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    with path.open('x', encoding='utf-8', newline='\n') as output:
        output.write(report)
    uri = context['provider'].getUriForFile(
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
    from android.runnable import run_on_ui_thread
    import threading

    completed = threading.Event()
    errors = []

    @run_on_ui_thread
    def launch():
        try:
            activity.startActivity(intent_type.createChooser(intent, title))
        except Exception as error:
            errors.append(error)
        finally:
            completed.set()

    launch()
    if not completed.wait(5):
        raise TimeoutError('Android share activity did not acknowledge launch')
    if errors:
        raise errors[0]
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
