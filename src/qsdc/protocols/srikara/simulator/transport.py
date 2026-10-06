"""Split a payload into protocol blocks, optionally protected by interleaved SECDED codewords."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from qsdc.common.error_correction import secded_decode, secded_encode


@dataclass(frozen=True)
class Block:
    offset: int
    bits: str
    symbols: tuple[str, ...]


def encode_blocks(payload: str, error_correction: str) -> list[Block]:
    """Uncoded blocks carry one 3-bit symbol; SECDED blocks carry 12 bits as 8 symbols."""
    if error_correction == "none":
        return [
            Block(i, payload[i : i + 3], (payload[i : i + 3].ljust(3, "0"),))
            for i in range(0, len(payload), 3)
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
    """Recover the block's payload bits, or None if SECDED detects an uncorrectable error."""
    if error_correction == "none":
        return "".join(symbols)[: len(block.bits)]

    data = [secded_decode("".join(lane)) for lane in zip(*symbols)]
    if None in data:
        return None
    return "".join(data)[: len(block.bits)]
