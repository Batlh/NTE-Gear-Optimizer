"""Validate the actual bundled font, source catalog and platform pins."""

import json
from pathlib import Path
from fontTools.ttLib import TTFont

root = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(root / 'src'))
from nte_gear_optimizer_app import texts

font = TTFont(root / 'src/nte_gear_optimizer_app/assets/DejaVuSans.ttf')
cmap = font.getBestCmap()
required = set('ÄÖÜäöüß±√↔Δ')
assert all(ord(ch) in cmap for ch in required)
strings = []
for value in vars(texts).values():
    if isinstance(value, str):
        strings.append(value)
    elif isinstance(value, dict):
        strings.extend(v for v in value.values() if isinstance(v, str))
assert all(ord(ch) in cmap for text in strings for ch in text if not ch.isspace()), (
    sorted(
        {
            ch
            for text in strings
            for ch in text
            if not ch.isspace() and ord(ch) not in cmap
        }
    )
)
catalog = json.loads(
    (root / 'src/nte_gear_optimizer_app/assets/catalog.json').read_text(
        encoding='utf-8'
    )
)
assert len(catalog['Characters']) == 26 and len(catalog['Branches']) == 74
assert 'python3==3.14.2,hostpython3==3.14.2' in (root / 'buildozer.spec').read_text(
    encoding='utf-8'
)
print('Bundled font glyphs, data catalog and matching Android Python pins PASS')
