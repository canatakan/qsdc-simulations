"""Paper-style bit uniformization helpers."""

from __future__ import annotations

from qsdc.common.random.base import RandomSource


def uniformize_message_bits(bits: str, random_source: RandomSource) -> str:
    mapping = {
        "0": ("01", "10"),
        "1": ("00", "11"),
    }
    return "".join(random_source.choice(mapping[bit]) for bit in bits)


def uniformize_block_bits(bits: str, random_source: RandomSource) -> str:
    mapping = {
        "0": ("00", "01"),
        "1": ("10", "11"),
    }
    return "".join(random_source.choice(mapping[bit]) for bit in bits)
