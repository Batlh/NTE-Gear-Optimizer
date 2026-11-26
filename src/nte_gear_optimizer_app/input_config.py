"""Platform input setup, isolated from Kivy for direct regression tests."""


def configure_input(config, platform):
    if platform == 'android':
        # SDL already supplies real finger events on Android. Re-adding the
        # desktop mouse provider duplicates the SAME gesture and breaks grabs.
        # Also remove the option from a config persisted by an older test APK.
        config.remove_option('input', 'mouse')
    else:
        config.set('input', 'mouse', 'mouse,multitouch_on_demand')
