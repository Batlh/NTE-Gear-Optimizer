[app]
title = NTE Gear Optimizer
package.name = nte_gear_optimizer
package.domain = io.github.batlh
source.dir = build/android_source
source.include_exts = py,json,ttf,txt,md,png
version = 0.29.0
requirements = python3==3.14.2,hostpython3==3.14.2,kivy==2.3.2
icon.filename = src/nte_gear_optimizer_app/assets/icons/kiwi_icon_512.png
icon.adaptive_foreground.filename = src/nte_gear_optimizer_app/assets/icons/kiwi_adaptive_foreground_432.png
icon.adaptive_background.filename = src/nte_gear_optimizer_app/assets/icons/kiwi_adaptive_background_432.png
orientation = portrait
fullscreen = 0
android.permissions =
android.extra_manifest_application_arguments = android/debug_provider.xml
android.add_resources = android/res/xml/nte_debug_paths.xml:xml/nte_debug_paths.xml
android.add_src = android/java
android.enable_androidx = True
android.gradle_dependencies = androidx.core:core:1.15.0
android.api = 35
android.minapi = 24
android.ndk = 28c
android.ndk_api = 24
android.archs = arm64-v8a
android.accept_sdk_license = True
p4a.branch = develop
p4a.commit = 9562d1b4f306d0af1e76991c711114010dea4152
p4a.local_recipes = build_recipes
p4a.bootstrap = sdl2

[buildozer]
log_level = 2
warn_on_root = 0
