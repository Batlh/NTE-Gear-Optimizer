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


def image_data(data):
    """Validate canonical PNG bytes; compare pixels independent of zlib encoding.

    Published source PNGs stay byte-identical on every platform. Regeneration
    may use a different linked zlib encoder; that is not a different image.
    """
    assert data.startswith(b'\x89PNG\r\n\x1a\n')
    offset = 8
    header = None
    payload = b''
    ended = False
    while offset < len(data):
        n = struct.unpack('!I', data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        body = data[offset + 8 : offset + 8 + n]
        assert len(body) == n
        crc = struct.unpack('!I', data[offset + 8 + n : offset + 12 + n])[0]
        assert crc == zlib.crc32(kind + body)
        if kind == b'IHDR':
            assert header is None
            header = body
        elif kind == b'IDAT':
            payload += body
        elif kind == b'IEND':
            assert not body
            ended = True
        else:
            raise AssertionError('Unexpected UI PNG chunk')
        offset += n + 12
    assert ended and offset == len(data) and len(header) == 13
    width, height, depth, color, compression, filtering, interlace = struct.unpack(
        '!IIBBBBB', header
    )
    assert (
        depth == 8 and color == 6 and (compression, filtering, interlace) == (0, 0, 0)
    )
    raw = zlib.decompress(payload)
    assert len(raw) == height * (1 + width * 4)
    assert all(raw[y * (1 + width * 4)] == 0 for y in range(height))
    return header, raw


def colored_outputs():
    import json

    colors = json.loads(
        (Path(__file__).resolve().parents[1] / 'design/design_tokens.json').read_text(
            encoding='utf-8'
        )
    )['colors']

    def rgb(name):
        if name is None:
            return None
        v = colors[name].lstrip('#')
        return tuple(int(v[i : i + 2], 16) for i in (0, 2, 4))

    styles = {
        'outline_normal': (12, 'surface', 'border'),
        'outline_down': (12, 'surface2', 'accent'),
        'primary_normal': (12, 'accent', None),
        'primary_down': (12, 'accent_text', None),
        'pill_normal': (24, 'surface', 'accent'),
        'pill_down': (24, 'surface2', 'accent'),
        'text_normal': (12, None, None),
        'text_down': (12, 'surface2', None),
        'input_normal': (10, 'background', 'border'),
        'input_focus': (10, 'background', 'accent'),
    }
    results = {}
    for style, (radius, fill, edge) in styles.items():
        # Reuse the deterministic white alpha masks; compose each palette pair
        # once into a single straight-alpha PNG. Runtime draws ONE native patch.
        def pixels(data):
            pos = 8
            payload = b''
            while pos < len(data):
                n = struct.unpack('!I', data[pos : pos + 4])[0]
                if data[pos + 4 : pos + 8] == b'IDAT':
                    payload += data[pos + 8 : pos + 8 + n]
                pos += n + 12
            return zlib.decompress(payload)

        outer = pixels(png(radius, False))
        ring = pixels(png(radius, True))
        side = (radius * 2 + 3) * 4
        raw = bytearray()
        f = rgb(fill)
        e = rgb(edge)
        for y in range(side):
            raw.append(0)
            for x in range(side):
                i = y * (1 + side * 4) + 1 + x * 4 + 3
                a = outer[i] / 255
                ea = ring[i] / 255 if e else 0
                fa = (a - ea) if e else a
                if f is None:
                    fa = 0
                alpha = fa + ea
                channels = tuple(
                    round(((f[c] if f else 0) * fa + (e[c] if e else 0) * ea) / alpha)
                    if alpha
                    else 0
                    for c in range(3)
                )
                raw.extend((*channels, round(alpha * 255)))
        data = (
            b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('!IIBBBBB', side, side, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9))
            + chunk(b'IEND', b'')
        )
        results[style + '.png'] = data
    return results


if __name__ == '__main__':
    out = (
        Path(__file__).resolve().parents[1]
        / 'src/nte_gear_optimizer_app/assets/ui_masks'
    )
    out.mkdir(parents=True, exist_ok=True)
    for name, data in (outputs() | colored_outputs()).items():
        p = out / name
        if p.exists():
            assert image_data(p.read_bytes()) == image_data(data), p
        else:
            p.write_bytes(data)
    print('Own deterministic round UI masks and native palette patches verified')
