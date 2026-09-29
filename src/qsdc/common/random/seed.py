import hashlib


def derive_seed(*parts: object) -> int:
    """Derive a reproducible 32-bit seed for an independent random stream."""
    digest = hashlib.sha256()
    for part in parts:
        encoded = str(part).encode()
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
    return int.from_bytes(digest.digest()[:4], "big")
