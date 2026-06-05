"""Stable seed derivation for benchmark trials."""

from __future__ import annotations

import hashlib


def derive_seed(*parts: object) -> int:
    """Derive a reproducible unsigned 32-bit seed from arbitrary parts."""

    digest = hashlib.sha256()
    for part in parts:
        encoded = str(part).encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
    return int.from_bytes(digest.digest()[:4], "big")
