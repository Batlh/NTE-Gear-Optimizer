[app]
title = NTE Gear Optimizer
package.name = nte_gear_optimizer
package.domain = io.github.batlh
source.dir = build/android_source
source.include_exts = py,json,ttf,txt,md,png
version = 0.29.0
requirements = python3==3.14.2,hostpython3==3.14.2,kivy==2.3.2
icon.filename = src/nte_gear_optimizer_app/assets/placeholder.png
orientation = portrait
fullscreen = 0
android.permissions =
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
