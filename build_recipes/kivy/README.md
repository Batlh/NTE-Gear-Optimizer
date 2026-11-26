# Pinned Kivy recipe

Revision 0 · 2026-11-26 · Status: build input · replaces no prior file

The upstream recipe is retained in upstream_recipe.txt, with its exact p4a
commit in recipe.diff. Changes are version 2.3.2, pinned modern Cython for
Python 3.14, and removal of no-ast-str.patch: Kivy 2.3.2 already contains this
parser fix. Patches are applied by p4a through this source-controlled recipe.
No manual edit or reset in a build tree is part of the build procedure.
The remaining patch files are byte-bound upstream inputs. The removed patch
is kept for review only. Kivy and p4a are MIT licensed.
