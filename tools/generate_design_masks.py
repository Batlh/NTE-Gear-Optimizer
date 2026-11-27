"""Deterministic own UI alpha masks, not third-party artwork. MIT like this project."""

import math, struct, zlib
from pathlib import Path


def chunk(kind, data):
    return (
        struct.pack('!I', len(data))
        + kind
        + data
        + struct.pack('!I', zlib.crc32(kind + data))
    )


def png(radius, edge):
    scale = 4
    side = (radius * 2 + 3) * scale
    center = side / 2

    def coverage(x, y, inset):
        r = (radius - inset) * scale
        extent = center - inset * scale
        qx = abs(x - center) - (extent - r)
        qy = abs(y - center) - (extent - r)
        distance = math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - r
        return max(0, min(1, 0.5 - distance))

    raw = bytearray()
    for y in range(side):
        raw.append(0)
        for x in range(side):
            a = coverage(x + 0.5, y + 0.5, 0)
            if edge:
                a = max(0, a - coverage(x + 0.5, y + 0.5, 1))
            raw.extend((255, 255, 255, round(255 * a)))
    return (
        b'\x89PNG\r\n\x1a\n'
        + chunk(b'IHDR', struct.pack('!IIBBBBB', side, side, 8, 6, 0, 0, 0))
        + chunk(b'IDAT', zlib.compress(raw, 9))
        + chunk(b'IEND', b'')
    )


def outputs():
    return {
        f'round_{kind}_r{r}.png': png(r, kind == 'edge')
        for r in (10, 12, 24)
        for kind in ('fill', 'edge')
    }


if __name__ == '__main__':
    out = (
        Path(__file__).resolve().parents[1]
        / 'src/nte_gear_optimizer_app/assets/ui_masks'
    )
    out.mkdir(parents=True, exist_ok=True)
    for name, data in outputs().items():
        p = out / name
        if p.exists():
            assert p.read_bytes() == data, p
        else:
            p.write_bytes(data)
    print('Own deterministic round UI masks verified')
