from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from qsdc.common.coding.error_correction import parity_decode, parity_encode
from qsdc.common.coding.intervals import GaussianIntervalCode, binary_labels
from qsdc.common.random import RandomSource
from qsdc.protocols.cao.config import SimulatorConfig

MESSAGE_CODEWORDS = {"0": ("01", "10"), "1": ("00", "11")}
BLOCK_CODEWORDS = {"0": ("00", "01"), "1": ("10", "11")}


def uniformize_message(bits: str) -> str:
    seen = {"0": 0, "1": 0}
    pairs = []
    for bit in bits:
        pairs.append(MESSAGE_CODEWORDS[bit][seen[bit] % 2])
        seen[bit] += 1
    return "".join(pairs)


def restore_message(bits: str) -> str:
    return "".join(
        "1" if bits[i] == bits[i + 1] else "0" for i in range(0, len(bits), 2)
    )


def uniformize_block(bits: str, rng: RandomSource) -> str:
    return "".join(rng.choice(BLOCK_CODEWORDS[bit]) for bit in bits)


def restore_block(bits: str) -> str:
    return bits[::2]


@dataclass(frozen=True)
class Box:
    payload: str
    bits: str
    detection: tuple[int, ...]
    parity: str

    def unmap(self, bits: str) -> str:
        return "".join(bit for i, bit in enumerate(bits) if i not in self.detection)

    def detection_matches(self, bits: str) -> bool:
        return all(bits[i] == self.bits[i] for i in self.detection)

    def parity_matches(self, bits: str) -> bool:
        return parity_decode(bits + self.parity) is not None


def map_box(payload: str, detection_bits: int, rng: RandomSource) -> Box:
    width = len(payload) + detection_bits
    detection = tuple(sorted(rng.shuffled(range(width))[:detection_bits]))
    remaining = iter(payload)
    bits = "".join(
        rng.choice("01") if i in detection else next(remaining) for i in range(width)
    )
    return Box(payload, bits, detection, parity_encode(bits)[-1])


def interval_code(config: SimulatorConfig) -> GaussianIntervalCode:
    return GaussianIntervalCode.equiprobable(
        binary_labels(config.box_bits + config.detection_bits),
        sqrt(config.modulation_variance_snu),
    )
