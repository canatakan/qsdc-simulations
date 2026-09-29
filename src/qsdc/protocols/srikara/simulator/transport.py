"""Split a payload into protocol blocks, optionally protected by interleaved SECDED codewords."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from qsdc.common.error_correction import secded_decode, secded_encode

# SECDED stripe: 12 payload bits as three (8, 4) codewords, interleaved into 8 symbols.
STRIPE_BITS = 12
STRIPE_SYMBOLS = 8


@dataclass(frozen=True)
class Block:
    offset: int
    bits: str
    symbols: tuple[str, ...]


def encode_blocks(
    payload: str, error_correction: str, symbols_per_block: int = 1
) -> list[Block]:
    """Uncoded blocks carry `symbols_per_block` symbols; SECDED blocks carry whole stripes."""
    if error_correction == "none":
        size = 3 * symbols_per_block
        encode = _symbols
    else:
        size = STRIPE_BITS * max(1, symbols_per_block // STRIPE_SYMBOLS)
        encode = _secded_symbols
    blocks = []
    for offset in range(0, len(payload), size):
        bits = payload[offset : offset + size]
        blocks.append(Block(offset, bits, encode(bits)))
    return blocks


def decode_block(
    block: Block, symbols: Sequence[str], error_correction: str
) -> str | None:
    """Recover the block's payload bits, or None if SECDED detects an uncorrectable stripe."""
    if error_correction == "none":
        return "".join(symbols)[: len(block.bits)]

    data = []
    for start in range(0, len(symbols), STRIPE_SYMBOLS):
        stripe = symbols[start : start + STRIPE_SYMBOLS]
        data += [secded_decode("".join(lane)) for lane in zip(*stripe)]
    if None in data:
        return None
    return "".join(data)[: len(block.bits)]


def _symbols(bits: str) -> tuple[str, ...]:
    padded = bits.ljust(-(-len(bits) // 3) * 3, "0")
    return tuple(padded[i : i + 3] for i in range(0, len(padded), 3))


def _secded_symbols(bits: str) -> tuple[str, ...]:
    padded = bits.ljust(-(-len(bits) // STRIPE_BITS) * STRIPE_BITS, "0")
    symbols: list[str] = []
    for start in range(0, len(padded), STRIPE_BITS):
        stripe = padded[start : start + STRIPE_BITS]
        codewords = [secded_encode(stripe[i : i + 4]) for i in range(0, 12, 4)]
        # Symbol k carries bit k of all three codewords: one bad symbol costs each one bit.
        symbols += ["".join(column) for column in zip(*codewords)]
    return tuple(symbols)
