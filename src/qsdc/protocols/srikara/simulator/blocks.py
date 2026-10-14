from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from qsdc.common.coding.error_correction import (
    parity_decode,
    parity_encode,
    secded_decode,
    secded_encode,
    use_odd_parity,
)
from qsdc.common.transmission import BaseBlock


@dataclass(frozen=True)
class Block(BaseBlock):
    symbols: tuple[str, ...]

    @classmethod
    def encode(cls, payload: str, error_correction: str) -> list[Block]:
        width = {"none": 3, "parity": 2, "secded": 12}[error_correction]

        blocks = []
        for offset in range(0, len(payload), width):
            bits = payload[offset : offset + width]
            padded = bits.ljust(width, "0")
            if error_correction == "none":
                symbols = (padded,)
            elif error_correction == "parity":
                symbols = (parity_encode(padded, use_odd_parity(offset)),)
            else:
                # SECDED: three (8, 4) codewords, one bit of each in every symbol.
                codewords = [secded_encode(padded[i : i + 4]) for i in range(0, 12, 4)]
                symbols = tuple("".join(column) for column in zip(*codewords))
            blocks.append(cls(offset, bits, symbols))

        return blocks

    def decode(self, symbols: Sequence[str], error_correction: str) -> str | None:
        if error_correction == "none":
            return "".join(symbols)[: len(self.bits)]

        if error_correction == "parity":
            data = parity_decode(symbols[0], use_odd_parity(self.offset))
            return None if data is None else data[: len(self.bits)]

        data = [secded_decode("".join(lane)) for lane in zip(*symbols)]
        if None in data:
            return None

        return "".join(data)[: len(self.bits)]
