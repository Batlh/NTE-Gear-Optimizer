"""Chunked, checksummed CI-only UI observations; no application state writes."""

import base64
import hashlib
import json
import zlib


def encode_probe(state, sequence):
    payload = base64.b64encode(
        zlib.compress(json.dumps(state, ensure_ascii=True).encode('utf-8'))
    ).decode('ascii')
    if len(payload) <= 2800:
        return ['NTE_CI_STATE=' + payload]
    digest = hashlib.sha256(payload.encode('ascii')).hexdigest()
    chunks = [payload[i : i + 2000] for i in range(0, len(payload), 2000)]
    return [
        f'NTE_CI_CHUNK={sequence}:{index}:{len(chunks)}:{digest}:{part}'
        for index, part in enumerate(chunks)
    ]


def decode_probe(logs):
    latest = None
    pending = {}
    for line in logs.splitlines():
        if 'NTE_CI_STATE=' in line:
            payload = line.split('NTE_CI_STATE=', 1)[1].strip()
            latest = json.loads(
                zlib.decompress(base64.b64decode(payload, validate=True))
            )
        elif 'NTE_CI_CHUNK=' in line:
            sequence, index, total, digest, part = (
                line.split('NTE_CI_CHUNK=', 1)[1].strip().split(':', 4)
            )
            index, total = int(index), int(total)
            if not 0 <= index < total <= 256 or len(digest) != 64:
                raise ValueError('Invalid CI observation chunk header')
            key = (sequence, digest, total)
            group = pending.setdefault(key, {})
            if index in group and group[index] != part:
                raise ValueError('Conflicting CI observation chunk')
            group[index] = part
            if len(group) == total:
                payload = ''.join(group[i] for i in range(total))
                if hashlib.sha256(payload.encode('ascii')).hexdigest() != digest:
                    raise ValueError('CI observation checksum mismatch')
                latest = json.loads(
                    zlib.decompress(base64.b64decode(payload, validate=True))
                )
                pending.pop(key)
    if latest is None:
        raise AssertionError('No complete checksummed emulator-only UI observation')
    return latest
