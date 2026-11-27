"""Own PNG UI masks are reproducible and correctly framed without image libraries."""

import importlib.util, struct, zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'design_mask_generator', ROOT / 'tools/generate_design_masks.py'
)
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


def test_masks_match_generator_pixels_and_valid_canonical_encoding():
    for name, data in generator.outputs().items():
        assert generator.image_data(
            (ROOT / 'src/nte_gear_optimizer_app/assets/ui_masks' / name).read_bytes()
        ) == generator.image_data(data)
        assert data.startswith(b'\x89PNG\r\n\x1a\n')
        width, height, depth, kind, compression, filtering, interlace = struct.unpack(
            '!IIBBBBB', data[16:29]
        )
        assert (
            width == height
            and depth == 8
            and kind == 6
            and (compression, filtering, interlace) == (0, 0, 0)
        )
        offset = 8
        while offset < len(data):
            length = struct.unpack('!I', data[offset : offset + 4])[0]
            chunk = data[offset + 4 : offset + 8]
            payload = data[offset + 8 : offset + 8 + length]
            assert struct.unpack(
                '!I', data[offset + 8 + length : offset + 12 + length]
            )[0] == zlib.crc32(chunk + payload)
            if chunk == b'IDAT':
                pixels = zlib.decompress(payload)
                assert len(pixels) == height * (1 + 4 * width)

                def at(x, y):
                    return pixels[y * (1 + width * 4) + 1 + x * 4 + 3]

                assert at(0, 0) == 0
                assert at(width // 2, height // 2) == (0 if 'edge' in name else 255)
            offset += length + 12
        assert offset == len(data)


def test_native_palette_patches_are_token_exact_and_reproducible():
    import json

    colors = json.loads(
        (ROOT / 'design/design_tokens.json').read_text(encoding='utf-8')
    )['colors']
    expected = {
        'outline_normal': 'surface',
        'outline_down': 'surface2',
        'primary_normal': 'accent',
        'primary_down': 'accent_text',
        'pill_normal': 'surface',
        'pill_down': 'surface2',
        'text_down': 'surface2',
        'input_normal': 'background',
        'input_focus': 'background',
    }
    for name, data in generator.colored_outputs().items():
        assert generator.image_data(
            (ROOT / 'src/nte_gear_optimizer_app/assets/ui_masks' / name).read_bytes()
        ) == generator.image_data(data)
        width, height = struct.unpack('!II', data[16:24])
        offset = 8
        compressed = b''
        while offset < len(data):
            length = struct.unpack('!I', data[offset : offset + 4])[0]
            if data[offset + 4 : offset + 8] == b'IDAT':
                compressed += data[offset + 8 : offset + 8 + length]
            offset += length + 12
        pixels = zlib.decompress(compressed)
        i = (height // 2) * (1 + 4 * width) + 1 + (width // 2) * 4
        if name == 'text_normal.png':
            assert pixels[i + 3] == 0
        else:
            code = colors[expected[name.removesuffix('.png')]].lstrip('#')
            assert tuple(pixels[i : i + 4]) == (
                *tuple(int(code[n : n + 2], 16) for n in (0, 2, 4)),
                255,
            )
