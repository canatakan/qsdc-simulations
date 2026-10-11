from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from qsdc.common import transmission
from qsdc.common.coding.error_correction import (
    parity_decode,
    parity_encode,
    secded_decode,
    secded_encode,
)


@dataclass(frozen=True)
class Block(transmission.Block):
    symbols: tuple[str, ...]


def odd_parity(offset: int) -> bool:
    return offset % 4 == 0


def encode_blocks(payload: str, error_correction: str) -> list[Block]:
    if error_correction == "none":
        return [
            Block(i, payload[i : i + 3], (payload[i : i + 3].ljust(3, "0"),))
            for i in range(0, len(payload), 3)
        ]
    if error_correction == "parity":
        return [
            Block(
                i,
                payload[i : i + 2],
                (parity_encode(payload[i : i + 2].ljust(2, "0"), odd_parity(i)),),
            )
            for i in range(0, len(payload), 2)
        ]

    blocks = []
    for offset in range(0, len(payload), 12):
        bits = payload[offset : offset + 12]
        padded = bits.ljust(12, "0")
        codewords = [secded_encode(padded[i : i + 4]) for i in range(0, 12, 4)]
        symbols = tuple("".join(column) for column in zip(*codewords))
        blocks.append(Block(offset, bits, symbols))
    return blocks


def decode_block(
    block: Block, symbols: Sequence[str], error_correction: str
) -> str | None:
    if error_correction == "none":
        return "".join(symbols)[: len(block.bits)]
    if error_correction == "parity":
        data = parity_decode(symbols[0], odd_parity(block.offset))
        return None if data is None else data[: len(block.bits)]

    data = [secded_decode("".join(lane)) for lane in zip(*symbols)]
    if None in data:
        return None
    return "".join(data)[: len(block.bits)]
