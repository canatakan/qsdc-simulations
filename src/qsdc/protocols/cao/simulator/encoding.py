"""Paper-style bit uniformization helpers."""

from __future__ import annotations

from dataclasses import dataclass
from math import inf, sqrt
from statistics import NormalDist

from qsdc.common import gaussian
from qsdc.common.random.base import RandomSource


@dataclass(frozen=True)
class EncodedBox:
    """A paper-style payload box with detection and odd-parity bits."""

    payload_bits: str
    mapping_bits: str
    detection_positions: tuple[int, ...]
    detection_bits: str
    parity_bit: int

    @property
    def codeword(self) -> str:
        return f"{self.mapping_bits}{self.parity_bit}"


@dataclass(frozen=True)
class DecodedBox:
    payload_bits: str
    detection_valid: bool
    parity_valid: bool

    @property
    def valid(self) -> bool:
        return self.detection_valid and self.parity_valid


def gaussian_encoding(
    box_bit_length: int,
    variance: float,
) -> gaussian.GaussianEncoding:
    symbol_count = 2**box_bit_length
    bit_labels = [
        f"{symbol_index:0{box_bit_length}b}"
        for symbol_index in range(symbol_count)
    ]
    return gaussian.get_gaussian_encoding(bit_labels, variance=variance)


def interval_for_bits(
    bits: str,
    encoding: gaussian.GaussianEncoding,
) -> gaussian.EncodingInterval:
    for interval in encoding.intervals:
        if interval.bits == bits:
            return interval
    raise ValueError(f"unknown encoding symbol {bits!r}")


def bits_for_real(value: float, encoding: gaussian.GaussianEncoding) -> str:
    for interval in encoding.intervals:
        if interval.contains(value):
            return interval.bits
    if value == inf:
        return encoding.intervals[-1].bits
    raise ValueError(
        f"value {value!r} was not found in any encoding interval; "
        "review the interval configuration"
    )


def sample_gaussian(variance: float, random_source: RandomSource) -> float:
    distribution = NormalDist(mu=0.0, sigma=sqrt(variance))
    probability = random_source.uniform(1e-15, 1.0 - 1e-15)
    return distribution.inv_cdf(probability)


def sample_gaussian_from_interval(
    interval: gaussian.EncodingInterval,
    variance: float,
    random_source: RandomSource,
) -> float:
    distribution = NormalDist(mu=0.0, sigma=sqrt(variance))
    probability = random_source.uniform(
        distribution.cdf(interval.lower),
        distribution.cdf(interval.upper),
    )
    probability = min(max(probability, 1e-15), 1.0 - 1e-15)
    return distribution.inv_cdf(probability)


def uniformize_message_bits(bits: str) -> str:
    """Apply Cao's alternating code conversion to a message bitstream."""

    _validate_bits(bits)
    mapping = {"0": ("01", "10"), "1": ("00", "11")}
    occurrences = {"0": 0, "1": 0}
    codewords = []
    for bit in bits:
        codewords.append(mapping[bit][occurrences[bit] % 2])
        occurrences[bit] += 1
    return "".join(codewords)


def uniformize_block_bits(bits: str, random_source: RandomSource) -> str:
    _validate_bits(bits)
    mapping = {
        "0": ("00", "01"),
        "1": ("10", "11"),
    }
    return "".join(random_source.choice(mapping[bit]) for bit in bits)


def restore_message_bits(bits: str) -> str:
    """Invert message uniformization, rejecting unknown codewords."""

    mapping = {"01": "0", "10": "0", "00": "1", "11": "1"}
    return _decode_pairs(bits, mapping, "message-uniformized")


def restore_block_bits(bits: str) -> str:
    """Invert block uniformization; its first code bit carries the value."""

    mapping = {"00": "0", "01": "0", "10": "1", "11": "1"}
    return _decode_pairs(bits, mapping, "block-uniformized")


def encode_box(
    payload_bits: str,
    detection_bit_count: int,
    random_source: RandomSource,
) -> EncodedBox:
    """Insert random detection bits and append an odd-parity check bit."""

    _validate_bits(payload_bits)
    if detection_bit_count <= 0:
        raise ValueError("detection_bit_count must be positive")

    mapping_width = len(payload_bits) + detection_bit_count
    detection_positions = tuple(
        sorted(
            random_source.shuffled(tuple(range(mapping_width)))[
                :detection_bit_count
            ]
        )
    )
    detection_bits = "".join(
        random_source.choice(("0", "1")) for _ in detection_positions
    )
    detection_by_position = dict(zip(detection_positions, detection_bits))
    payload = iter(payload_bits)
    mapping_bits = "".join(
        detection_by_position[position]
        if position in detection_by_position
        else next(payload)
        for position in range(mapping_width)
    )
    parity_bit = 1 if mapping_bits.count("1") % 2 == 0 else 0
    return EncodedBox(
        payload_bits=payload_bits,
        mapping_bits=mapping_bits,
        detection_positions=detection_positions,
        detection_bits=detection_bits,
        parity_bit=parity_bit,
    )


def decode_box(
    mapping_bits: str,
    detection_positions: tuple[int, ...],
    detection_bits: str,
    parity_bit: int,
) -> DecodedBox:
    """Remove announced detection bits and validate detection/parity checks."""

    _validate_bits(mapping_bits)
    if parity_bit not in (0, 1):
        raise ValueError("parity_bit must be 0 or 1")
    if len(detection_positions) != len(detection_bits):
        raise ValueError("detection positions and bits must have equal length")
    if len(set(detection_positions)) != len(detection_positions):
        raise ValueError("detection positions must be unique")
    if any(
        position < 0 or position >= len(mapping_bits)
        for position in detection_positions
    ):
        raise ValueError("detection position is outside the mapped box")

    detection_by_position = dict(zip(detection_positions, detection_bits))
    observed_detection = "".join(
        mapping_bits[position] for position in detection_positions
    )
    payload_bits = "".join(
        bit for position, bit in enumerate(mapping_bits)
        if position not in detection_by_position
    )
    return DecodedBox(
        payload_bits=payload_bits,
        detection_valid=observed_detection == detection_bits,
        parity_valid=(mapping_bits.count("1") + parity_bit) % 2 == 1,
    )


def _decode_pairs(bits: str, mapping: dict[str, str], label: str) -> str:
    _validate_bits(bits)
    if len(bits) % 2:
        raise ValueError(
            f"{label} bitstream must contain complete 2-bit codewords"
        )
    return "".join(
        mapping[bits[index:index + 2]]
        for index in range(0, len(bits), 2)
    )


def _validate_bits(bits: str) -> None:
    if any(bit not in "01" for bit in bits):
        raise ValueError("bitstream must contain only '0' and '1'")
