"""Three-bit interval encoding from the CV QSDC paper."""

from __future__ import annotations

from math import inf

from qsdc.common.random.base import RandomSource

from qsdc.common.gaussian import (
    EncodingInterval,
    GaussianEncoding,
    get_gaussian_encoding,
)

GRAY_CODED_BITS = ["000", "001", "011", "010", "110", "100", "101", "111"]

ENCODING_INTERVALS: dict[str, GaussianEncoding] = {
    "default": GaussianEncoding(
        intervals=(
            EncodingInterval("000", -inf, -3.0),
            EncodingInterval("001", -3.0, -2.0),
            EncodingInterval("010", -2.0, -1.0),
            EncodingInterval("011", -1.0, 0.0),
            EncodingInterval("100", 0.0, 1.0),
            EncodingInterval("101", 1.0, 2.0),
            EncodingInterval("110", 2.0, 3.0),
            EncodingInterval("111", 3.0, inf),
        ),
        tail_width=1.0,
    ),
    "optimized_v4": get_gaussian_encoding(GRAY_CODED_BITS, variance=4.0),
    "optimized_v8": get_gaussian_encoding(GRAY_CODED_BITS, variance=8.0),
    "optimized_v12": get_gaussian_encoding(GRAY_CODED_BITS, variance=12.0),
}


def validate_bits(bits: str) -> None:
    if len(bits) != 3 or any(bit not in "01" for bit in bits):
        raise ValueError(f"expected a 3-bit string, got {bits!r}")


def interval_for_bits(
    bits: str,
    intervals: str = "default",
) -> EncodingInterval:
    """Return the paper's real interval for one 3-bit symbol."""

    validate_bits(bits)
    for interval in ENCODING_INTERVALS[intervals].intervals:
        if interval.bits == bits:
            return interval
    raise ValueError(f"unknown 3-bit symbol {bits!r}")


def bits_for_real(value: float, intervals: str = "default") -> str:
    """Decode a real number by locating its paper interval."""

    for interval in ENCODING_INTERVALS[intervals].intervals:
        if interval.contains(value):
            return interval.bits
    raise ValueError(
        f"value {value!r} was not found in any encoding interval; "
        "review the interval configuration"
    )


def sample_message_value(
    bits: str,
    random_source: RandomSource,
    intervals: str = "default",
) -> float:
    """Choose m from the interval for bits."""

    tail_width = ENCODING_INTERVALS[intervals].tail_width
    interval = interval_for_bits(bits, intervals=intervals)
    if interval.lower == -inf:
        return random_source.uniform(interval.upper - tail_width, interval.upper)
    if interval.upper == inf:
        return random_source.uniform(interval.lower, interval.lower + tail_width)
    return random_source.uniform(interval.lower, interval.upper)


def beta_for_message_value(message_value: float) -> complex:
    """Return Alice's displacement beta = m(1 + i)."""

    return complex(message_value, message_value)
