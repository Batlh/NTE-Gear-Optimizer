"""Own PNG UI masks are reproducible and correctly framed without image libraries."""

import importlib.util, struct, zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'design_mask_generator', ROOT / 'tools/generate_design_masks.py'
)
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


def test_masks_match_deterministic_generator():
    for name, data in generator.outputs().items():
        assert (
            ROOT / 'src/nte_gear_optimizer_app/assets/ui_masks' / name
        ).read_bytes() == data
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
