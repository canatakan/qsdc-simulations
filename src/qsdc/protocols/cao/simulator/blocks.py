from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from qsdc.common.coding.universal_hash import UniversalHash
from qsdc.common.random import RandomSource
from qsdc.common.transmission import BaseBlock

from ..config import SimulatorConfig
from .mapping import (
    Box,
    restore_block,
    restore_message,
    uniformize_block,
    uniformize_message,
)
from .signals import Signal


@dataclass(frozen=True)
class Block(BaseBlock):
    uniformized: str | None = None
    payload: str | None = None

    @classmethod
    def encode(cls, payload: str, block_bits: int) -> list[Block]:
        padded = payload.ljust(-(-len(payload) // block_bits) * block_bits, "0")
        uniformized = uniformize_message(padded)

        blocks = []
        for i in range(0, len(payload), block_bits):
            message_part = uniformized[2 * i : 2 * (i + block_bits)]
            blocks.append(cls(i, payload[i : i + block_bits], uniformized=message_part))

        return blocks

    @classmethod
    def amplify(
        cls, payload: str, amplifier: UniversalHash, rng: RandomSource
    ) -> list[Block]:
        # The payload is a random input whose hash is the message, so the public
        # bits hide the message while they are fewer than the random bits.
        block_bits = amplifier.output_bits

        blocks = []
        for i in range(0, len(payload), block_bits):
            bits = payload[i : i + block_bits]
            randomness = "".join(rng.choice("01") for _ in range(amplifier.free_bits))
            hashed = amplifier.preimage(bits.ljust(block_bits, "0"), randomness)
            blocks.append(cls(i, bits, payload=hashed))

        return blocks

    def boxes(self, config: SimulatorConfig, rng: RandomSource) -> list[Box]:
        if self.payload is not None:
            bits = self.payload
        else:
            bits = uniformize_block(self.uniformized, rng)

        width = config.box_bits
        return [
            Box.map(bits[i : i + width], config.detection_bits, rng)
            for i in range(0, len(bits), width)
        ]

    def restore(self, signals: Sequence[Signal]) -> str | None:
        # Without reconciliation, Bob keeps the block only if every detection and
        # parity bit matches.
        if not all(signal.valid for signal in signals):
            return None

        payload = "".join(signal.decoded_payload for signal in signals)
        return restore_message(restore_block(payload))
