"""Map logical bits to Srikara symbols and back."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from qsdc.common.bits import chunk_bits
from qsdc.common.error_correction import Secded84, SecdedDecode
from qsdc.protocols.srikara.configuration.simulator import ErrorCorrection

LOGICAL_BITS_PER_FEC_BLOCK = 12
FEC_SYMBOLS_PER_BLOCK = 8
SECDED = Secded84()


@dataclass(frozen=True)
class TransportBlock:
    index: int
    payload_offset: int
    payload_bit_count: int
    encoded_bits: str
    symbols: tuple[str, ...]


@dataclass(frozen=True)
class TransportFrame:
    payload_bit_count: int
    padding_bit_count: int
    error_correction: ErrorCorrection
    blocks: tuple[TransportBlock, ...]

    @property
    def symbol_count(self) -> int:
        return sum(len(block.symbols) for block in self.blocks)

    @property
    def transmitted_bit_count(self) -> int:
        return 3 * self.symbol_count

    @property
    def first_attempt_state_count(self) -> int:
        return 4 * self.symbol_count

    @property
    def transport_block_count(self) -> int:
        return len(self.blocks)

    @property
    def coded_bit_count(self) -> int:
        if self.error_correction == "secded":
            return self.transmitted_bit_count
        return self.payload_bit_count

    @property
    def codeword_count(self) -> int:
        return 3 * len(self.blocks) if self.error_correction == "secded" else 0

    @property
    def nominal_code_rate(self) -> float:
        return 0.5 if self.error_correction == "secded" else 1.0

    @property
    def effective_code_rate(self) -> float:
        return self.payload_bit_count / self.transmitted_bit_count

    @property
    def overhead_bit_count(self) -> int:
        return self.transmitted_bit_count - self.payload_bit_count


@dataclass(frozen=True)
class TransportDecode:
    recovered_bits: Optional[str]
    codewords: tuple[SecdedDecode, ...] = ()

    @property
    def clean_codewords(self) -> int:
        return sum(codeword.status == "clean" for codeword in self.codewords)

    @property
    def corrected_codewords(self) -> int:
        return sum(codeword.status == "corrected" for codeword in self.codewords)

    @property
    def corrected_bits(self) -> int:
        return sum(codeword.corrected_bits for codeword in self.codewords)

    @property
    def recovered_erasures(self) -> int:
        return sum(codeword.recovered_erasures for codeword in self.codewords)

    @property
    def uncorrectable_codewords(self) -> int:
        return sum(codeword.status == "uncorrectable" for codeword in self.codewords)


def encode_payload(bits: str, error_correction: ErrorCorrection) -> TransportFrame:
    if error_correction == "none":
        return _uncoded_frame(bits)
    return _secded_frame(bits)


def decode_block(
    block: TransportBlock,
    decoded_symbols: Sequence[Optional[str]],
    error_correction: ErrorCorrection,
) -> TransportDecode:
    if error_correction == "none":
        recovered = None
        if all(symbol is not None for symbol in decoded_symbols):
            recovered = "".join(symbol or "" for symbol in decoded_symbols)
            recovered = recovered[: block.payload_bit_count]
        return TransportDecode(recovered)

    codewords = tuple(
        SECDED.decode(
            "".join(
                SECDED.ERASURE if symbol is None else symbol[lane]
                for symbol in decoded_symbols
            )
        )
        for lane in range(3)
    )
    recovered = None
    if all(codeword.data_bits is not None for codeword in codewords):
        recovered = "".join(codeword.data_bits or "" for codeword in codewords)
        recovered = recovered[: block.payload_bit_count]
    return TransportDecode(recovered, codewords)


def _uncoded_frame(bits: str) -> TransportFrame:
    symbols = chunk_bits(bits, 3)
    padding = (3 * len(symbols)) - len(bits)
    block = TransportBlock(0, 0, len(bits), "".join(symbols), symbols)
    return TransportFrame(len(bits), padding, "none", (block,))


def _secded_frame(bits: str) -> TransportFrame:
    padding = (-len(bits)) % LOGICAL_BITS_PER_FEC_BLOCK
    padded = bits + ("0" * padding)
    blocks = tuple(
        _secded_block(index, offset, padded[offset : offset + 12], len(bits))
        for index, offset in enumerate(range(0, len(padded), 12))
    )
    return TransportFrame(len(bits), padding, "secded", blocks)


def _secded_block(
    index: int,
    offset: int,
    source_bits: str,
    payload_bit_count: int,
) -> TransportBlock:
    codewords = tuple(
        SECDED.encode(source_bits[start : start + 4])
        for start in range(0, 12, 4)
    )
    symbols = tuple(
        "".join(codeword[position] for codeword in codewords) for position in range(8)
    )
    return TransportBlock(
        index=index,
        payload_offset=offset,
        payload_bit_count=min(12, payload_bit_count - offset),
        encoded_bits="".join(symbols),
        symbols=symbols,
    )
