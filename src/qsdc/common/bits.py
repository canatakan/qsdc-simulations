def hamming_distance(left: str, right: str) -> int:
    return sum(a != b for a, b in zip(left, right))


def bytes_to_bits(payload: bytes) -> str:
    return "".join(f"{byte:08b}" for byte in payload)


def bits_to_bytes(bits: str) -> bytes:
    return bytes(int(bits[i : i + 8], 2) for i in range(0, len(bits), 8))

