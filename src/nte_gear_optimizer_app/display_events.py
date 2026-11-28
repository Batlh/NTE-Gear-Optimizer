"""Android display notifications. Callbacks never read display properties."""


def subscribe(callback):
    from jnius import PythonJavaClass, java_method, autoclass, cast

    activity = autoclass('org.kivy.android.PythonActivity').mActivity
    manager = cast(
        'android.hardware.display.DisplayManager', activity.getSystemService('display')
    )

    class Listener(PythonJavaClass):
        __javainterfaces__ = ['android/hardware/display/DisplayManager$DisplayListener']
        __javacontext__ = 'app'

        @java_method('(I)V')
        def onDisplayChanged(self, identifier):
            callback('display_changed')

        @java_method('(I)V')
        def onDisplayAdded(self, identifier):
            callback('display_added')

        @java_method('(I)V')
        def onDisplayRemoved(self, identifier):
            callback('display_removed')

    listener = Listener()
    handler = autoclass('android.os.Handler')(
        autoclass('android.os.Looper').getMainLooper()
    )
    manager.registerDisplayListener(listener, handler)
    # Retain the Python proxy, Java handler and manager until explicit stop.
    return manager, listener, handler


def unsubscribe(subscription):
    manager, listener, handler = subscription
    manager.unregisterDisplayListener(listener)
