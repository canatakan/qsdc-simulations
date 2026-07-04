"""Three-bit interval encoding from the CV QSDC paper."""

from __future__ import annotations

from dataclasses import dataclass
from math import inf

from qsdc.common.random.base import RandomSource


@dataclass(frozen=True)
class EncodingInterval:
    """A real-line interval assigned to a 3-bit symbol."""

    bits: str
    lower: float
    upper: float

    def contains(self, value: float) -> bool:
        return self.lower < value < self.upper


DEFAULT_INTERVALS = "default"
OPTIMIZED_INTERVALS = "optimized"
INTERVAL_STRATEGIES = (DEFAULT_INTERVALS, OPTIMIZED_INTERVALS)


_DEFAULT_INTERVALS: tuple[EncodingInterval, ...] = (
    EncodingInterval("000", -inf, -3.0),
    EncodingInterval("001", -3.0, -2.0),
    EncodingInterval("010", -2.0, -1.0),
    EncodingInterval("011", -1.0, 0.0),
    EncodingInterval("100", 0.0, 1.0),
    EncodingInterval("101", 1.0, 2.0),
    EncodingInterval("110", 2.0, 3.0),
    EncodingInterval("111", 3.0, inf),
)

_OPTIMIZED_BOUNDS = (
    -inf,
    -3.25,
    -1.91,
    -0.90,
    0.0,
    0.90,
    1.91,
    3.25,
    inf,
)
_OPTIMIZED_BITS = ("000", "001", "011", "010", "110", "100", "101", "111")
_OPTIMIZED_INTERVALS = tuple(
    EncodingInterval(bits, lower, upper)
    for bits, lower, upper in zip(
        _OPTIMIZED_BITS,
        _OPTIMIZED_BOUNDS,
        _OPTIMIZED_BOUNDS[1:],
    )
)

INTERVALS = _DEFAULT_INTERVALS
INTERVALS_BY_STRATEGY = {
    DEFAULT_INTERVALS: _DEFAULT_INTERVALS,
    OPTIMIZED_INTERVALS: _OPTIMIZED_INTERVALS,
}


def validate_bits(bits: str) -> None:
    if len(bits) != 3 or any(bit not in "01" for bit in bits):
        raise ValueError(f"expected a 3-bit string, got {bits!r}")


def interval_for_bits(
    bits: str,
    intervals: str = DEFAULT_INTERVALS,
) -> EncodingInterval:
    """Return the paper's real interval for one 3-bit symbol."""

    validate_bits(bits)
    for interval in INTERVALS_BY_STRATEGY[intervals]:
        if interval.bits == bits:
            return interval
    raise ValueError(f"unknown 3-bit symbol {bits!r}")


def bits_for_real(value: float, intervals: str = DEFAULT_INTERVALS) -> str:
    """Decode a real number by locating its paper interval."""

    for interval in INTERVALS_BY_STRATEGY[intervals]:
        if interval.contains(value):
            return interval.bits
    raise ValueError(
        f"value {value!r} lies on an interval boundary and is not decodable"
    )


def sample_message_value(
    bits: str,
    random_source: RandomSource,
    tail_width: float = 1.0,
    intervals: str = DEFAULT_INTERVALS,
) -> float:
    """Choose m from the interval for bits."""

    interval = interval_for_bits(bits, intervals=intervals)
    if interval.lower == -inf:
        return random_source.uniform(interval.upper - tail_width, interval.upper)
    if interval.upper == inf:
        return random_source.uniform(interval.lower, interval.lower + tail_width)
    return random_source.uniform(interval.lower, interval.upper)


def beta_for_message_value(message_value: float) -> complex:
    """Return Alice's displacement beta = m(1 + i)."""

    return complex(message_value, message_value)
