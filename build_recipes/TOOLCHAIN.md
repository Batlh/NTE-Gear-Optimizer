# Android tooling versus application runtime

Revision 0 · 2026-11-26 · Status: pinned build input · replaces no earlier file

Buildozer 1.6.0 declares Cython<3. Its orchestration environment therefore uses
CPython 3.12.14 and Cython 0.29.37, as in the independently reviewed spike.
This environment does not run the application core. p4a builds its own
hostpython3==3.14.2 and python3==3.14.2, both explicitly pinned in buildozer.spec.
The Kivy recipe uses Cython 3.3.2 in that host-Python build environment.
The application's Python line remains 3.14 on all platforms; no dependency
resolver is bypassed and no third-party installed file is edited by hand.
