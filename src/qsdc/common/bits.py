"""Shared bitstream helpers."""

from __future__ import annotations

from qsdc.common.random.base import RandomSource


def hamming_distance(left: str, right: str) -> int:
    if len(left) != len(right):
        raise ValueError("bitstreams must have equal length")
    return sum(1 for left_bit, right_bit in zip(left, right) if left_bit != right_bit)


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


def weighted_random_bits(
    bit_count: int,
    one_probability: float,
    random_source: RandomSource,
) -> str:
    """Generate independent Bernoulli bits as a string."""

    if bit_count < 0:
        raise ValueError("bit_count must be non-negative")
    if not 0.0 <= one_probability <= 1.0:
        raise ValueError("one_probability must be between 0 and 1")
    return "".join(
        "1" if random_source.uniform(0.0, 1.0) < one_probability else "0"
        for _ in range(bit_count)
    )
