"""Bitstream comparison helpers."""

from __future__ import annotations


def hamming_distance(left: str, right: str) -> int:
    if len(left) != len(right):
        raise ValueError("bitstreams must have equal length")
    return sum(1 for left_bit, right_bit in zip(left, right) if left_bit != right_bit)
