from __future__ import annotations

import numpy as np


def hamming_distance(left: str, right: str) -> int:
    return sum(a != b for a, b in zip(left, right))


def bytes_to_bits(payload: bytes) -> str:
    return "".join(f"{byte:08b}" for byte in payload)


def bits_to_bytes(bits: str) -> bytes:
    return bytes(int(bits[i : i + 8], 2) for i in range(0, len(bits), 8))


def bits_to_array(bits: str) -> np.ndarray:
    return np.array([int(bit) for bit in bits], dtype=np.uint8)


def array_to_bits(values: np.ndarray) -> str:
    return "".join(str(int(value)) for value in values)
