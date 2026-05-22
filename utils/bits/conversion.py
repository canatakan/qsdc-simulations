"""Shared bitstream conversion helpers."""

from __future__ import annotations


def bytes_to_bits(payload: bytes) -> str:
    return "".join(f"{byte:08b}" for byte in payload)


def bits_to_bytes(bits: str) -> bytes:
    if len(bits) % 8 != 0:
        raise ValueError("bitstream length is not byte-aligned")
    return bytes(int(bits[index: index + 8], 2) for index in range(0, len(bits), 8))


def chunk_bits(bits: str, width: int, pad: str = "0") -> tuple[str, ...]:
    if width <= 0:
        raise ValueError("width must be positive")
    padding = (-len(bits)) % width
    padded = bits + (pad * padding)
    return tuple(padded[index: index + width] for index in range(0, len(padded), width))
