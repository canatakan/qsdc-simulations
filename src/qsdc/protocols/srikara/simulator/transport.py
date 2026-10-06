"""Split a payload into protocol blocks, optionally protected by parity or SECDED."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from qsdc.common.error_correction import (
    parity_decode,
    parity_encode,
    secded_decode,
    secded_encode,
)


@dataclass(frozen=True)
class Block:
    offset: int
    bits: str
    symbols: tuple[str, ...]


def encode_blocks(payload: str, error_correction: str) -> list[Block]:
    """A block is one symbol of 3 bits uncoded or 2 bits plus parity; with SECDED it is
    12 bits sent as 8 symbols."""
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
                (parity_encode(payload[i : i + 2].ljust(2, "0")),),
            )
            for i in range(0, len(payload), 2)
        ]

    blocks = []
    for offset in range(0, len(payload), 12):
        bits = payload[offset : offset + 12]
        padded = bits.ljust(12, "0")
        codewords = [secded_encode(padded[i : i + 4]) for i in range(0, 12, 4)]
        # Symbol k carries bit k of all three codewords: one bad symbol costs each one bit.
        symbols = tuple("".join(column) for column in zip(*codewords))
        blocks.append(Block(offset, bits, symbols))
    return blocks


def decode_block(
    block: Block, symbols: Sequence[str], error_correction: str
) -> str | None:
    """Recover the block's payload bits, or None if the code detects an uncorrectable error."""
    if error_correction == "none":
        return "".join(symbols)[: len(block.bits)]
    if error_correction == "parity":
        data = parity_decode(symbols[0])
        return None if data is None else data[: len(block.bits)]

    data = [secded_decode("".join(lane)) for lane in zip(*symbols)]
    if None in data:
        return None
    return "".join(data)[: len(block.bits)]
