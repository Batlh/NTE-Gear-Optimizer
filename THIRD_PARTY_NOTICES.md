# Third-party notices — NTE Gear Optimizer Phase 2A

Revision 0 · 2026-11-26 · Status: debug-build notices · replaces no prior file

This is an unofficial fan tool, not affiliated with, operated or supported by
Hotta Studio or Perfect World. No official artwork or logo is included. Names
and trademarks belong to their owners. MIT applies only to our own code.
Research/guide observations retain their separate provenance and rights; see
DATA_SOURCES.md in bundles (data/SOURCES.md in the repository).

## Runtime and bundled components

- CPython 3.14: Python Software Foundation License and included notices;
  third_party_licenses/CPython_PSF.txt.
- Kivy 2.3.2: MIT; third_party_licenses/Kivy_MIT.txt.
- SDL2 and SDL2 image/mixer/ttf bindings: zlib-style licenses, not our MIT grant.
  third_party_licenses/SDL2_zlib.txt includes the SDL license. Additional license
  files distributed by installed wheels are copied to wheel_notices in Windows.
- Roboto Regular: Copyright 2011 Google Inc.; Apache License 2.0, confirmed in
  the actual font's metadata. Font and license are both shipped. It covers the
  application's German characters, ± and √. No emoji or official game font.
- ANGLE 0.5.0 Windows dependency wheel: BSD-style ANGLE project license;
  its wheel notices are copied verbatim into wheel_notices in the bundle.
- Pillow: HPND-style PIL license and bundled codec notices, preserved from its
  wheel in Windows. JPEG/zlib/libpng/FreeType may be included by runtime wheels.
- OpenSSL: Apache License 2.0; third_party_licenses/OpenSSL_APACHE2.txt.
- PyInstaller 6.22.3 bootloader: GPL with its special distribution exception;
  third_party_licenses/PyInstaller_GPL_EXCEPTION.txt. The exception permits
  shipping this application under its own terms.
- Buildozer 1.6.0 and python-for-android: MIT, build tools. Cython and packaging
  tools are build dependencies, not a claim to ownership of their code.
- Windows platform runtime DLLs retain their vendor licenses. Any LGPL
  components brought by a wheel retain their own license; no third-party
  component is relicensed under our MIT license. Preserve the supplied notices.

The bundles carry exact file inventories. The build uses no release key,
signing secret or GitHub secret. Android uses only an automatically generated
debug signature; no keystore is distributed. Android device runtime is subject
to the user's later phone test, not asserted by a successful APK build.
