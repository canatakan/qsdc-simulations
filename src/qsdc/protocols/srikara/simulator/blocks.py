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
from qsdc.common.coding.ldpc import MAX_CONFIDENCE, LdpcCode
from qsdc.common.transmission import BaseBlock


@dataclass(frozen=True)
class CodingOptions:
    ldpc: LdpcCode | None = None
    confidences: Sequence[float] | None = None
    max_iterations: int = 100


@dataclass(frozen=True)
class Block(BaseBlock):
    symbols: tuple[str, ...]

    @staticmethod
    def encode(
        payload: str, error_correction: str, options: CodingOptions | None = None
    ) -> list[Block]:
        if error_correction == "none":
            return Block._encode_none(payload)
        elif error_correction == "parity":
            return Block._encode_parity(payload)
        elif error_correction == "secded":
            return Block._encode_secded(payload)
        else:
            return Block._encode_ldpc(payload, options.ldpc)

    def decode(
        self,
        symbols: Sequence[str],
        error_correction: str,
        options: CodingOptions | None = None,
    ) -> str | None:
        if error_correction == "none":
            data = self._decode_none(symbols)
        elif error_correction == "parity":
            data = self._decode_parity(symbols)
        elif error_correction == "secded":
            data = self._decode_secded(symbols)
        else:
            data = self._decode_ldpc(
                options.confidences, options.ldpc, options.max_iterations
            )

        return None if data is None else data[: len(self.bits)]

    @staticmethod
    def _encode_none(payload: str) -> list[Block]:
        blocks = []
        for offset in range(0, len(payload), 3):
            bits = payload[offset : offset + 3]
            blocks.append(Block(offset, bits, (bits.ljust(3, "0"),)))

        return blocks

    @staticmethod
    def _decode_none(symbols: Sequence[str]) -> str:
        return "".join(symbols)

    @staticmethod
    def _encode_parity(payload: str) -> list[Block]:
        blocks = []
        for offset in range(0, len(payload), 2):
            bits = payload[offset : offset + 2]
            symbols = (parity_encode(bits.ljust(2, "0"), use_odd_parity(offset)),)
            blocks.append(Block(offset, bits, symbols))

        return blocks

    def _decode_parity(self, symbols: Sequence[str]) -> str | None:
        return parity_decode(symbols[0], use_odd_parity(self.offset))

    @staticmethod
    def _encode_secded(payload: str) -> list[Block]:
        blocks = []
        for offset in range(0, len(payload), 12):
            bits = payload[offset : offset + 12]
            padded = bits.ljust(12, "0")

            # Three (8, 4) codewords, one bit of each in every symbol.
            codewords = [secded_encode(padded[i : i + 4]) for i in range(0, 12, 4)]
            symbols = tuple("".join(column) for column in zip(*codewords))
            blocks.append(Block(offset, bits, symbols))

        return blocks

    @staticmethod
    def _decode_secded(symbols: Sequence[str]) -> str | None:
        data = [secded_decode("".join(lane)) for lane in zip(*symbols)]

        return None if None in data else "".join(data)

    @staticmethod
    def _encode_ldpc(payload: str, code: LdpcCode) -> list[Block]:
        blocks = []
        for offset in range(0, len(payload), code.data_bits):
            bits = payload[offset : offset + code.data_bits]
            encoded = code.encode(bits.ljust(code.data_bits, "0"))

            symbols = tuple(encoded[i : i + 3] for i in range(0, len(encoded), 3))
            blocks.append(Block(offset, bits, symbols))

        return blocks

    def _decode_ldpc(
        self, confidences: Sequence[float], code: LdpcCode, max_iterations: int
    ) -> str | None:
        # With no observations, a zero syndrome alone cannot establish delivery.
        if not any(confidences):
            return None

        prior = list(confidences)
        prior[len(self.bits) : code.data_bits] = [MAX_CONFIDENCE] * (
            code.data_bits - len(self.bits)
        )

        decoded = code.decode(prior, "0" * code.checks, max_iterations)
        if decoded is None or "1" in decoded[len(self.bits) : code.data_bits]:
            return None

        return decoded
