"""Small binary forward-error-correction primitives."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Iterable, Literal, Optional

DecodeStatus = Literal["clean", "corrected", "uncorrectable"]


@dataclass(frozen=True)
class SecdedDecode:
    """Bounded-distance result for one extended Hamming codeword."""

    data_bits: Optional[str]
    status: DecodeStatus
    corrected_bits: int = 0
    recovered_erasures: int = 0


class Secded84:
    """Systematic extended Hamming SECDED (8, 4, 4), with even parity."""

    data_bits = 4
    encoded_bits = 8
    minimum_distance = 4
    ERASURE = "?"

    def encode(self, bits: str) -> str:
        if len(bits) != self.data_bits or any(bit not in "01" for bit in bits):
            raise ValueError("SECDED input must be four binary bits")

        d0, d1, d2, d3 = (int(bit) for bit in bits)
        word = [0] * self.encoded_bits
        word[2], word[4], word[5], word[6] = d0, d1, d2, d3
        word[0] = d0 ^ d1 ^ d3
        word[1] = d0 ^ d2 ^ d3
        word[3] = d1 ^ d2 ^ d3
        word[7] = _xor(word[:7])
        return "".join(str(bit) for bit in word)

    def decode(self, bits: str) -> SecdedDecode:
        """Decode a codeword; ``?`` represents an erased bit."""

        if len(bits) != self.encoded_bits or any(bit not in "01?" for bit in bits):
            raise ValueError("SECDED codeword must be eight bits or erasures")

        if self.ERASURE in bits:
            return self._decode_erasures(bits)

        word = [int(bit) for bit in bits]
        syndrome = (
            _xor(word[index - 1] for index in (1, 3, 5, 7))
            | (_xor(word[index - 1] for index in (2, 3, 6, 7)) << 1)
            | (_xor(word[index - 1] for index in (4, 5, 6, 7)) << 2)
        )
        parity = _xor(word)

        if syndrome == 0 and parity == 0:
            status: DecodeStatus = "clean"
            corrected_bits = 0
        elif syndrome != 0 and parity == 1:
            word[syndrome - 1] ^= 1
            status = "corrected"
            corrected_bits = 1
        elif syndrome == 0 and parity == 1:
            word[7] ^= 1
            status = "corrected"
            corrected_bits = 1
        else:
            return SecdedDecode(None, "uncorrectable")

        data_bits = "".join(str(word[position]) for position in (2, 4, 5, 6))
        return SecdedDecode(data_bits, status, corrected_bits)

    def _decode_erasures(self, bits: str) -> SecdedDecode:
        erasures = bits.count(self.ERASURE)
        candidates: list[tuple[str, int]] = []
        for data in product("01", repeat=self.data_bits):
            data_bits = "".join(data)
            codeword = self.encode(data_bits)
            errors = sum(
                observed != self.ERASURE and observed != candidate
                for observed, candidate in zip(bits, codeword)
            )
            if (2 * errors) + erasures < self.minimum_distance:
                candidates.append((data_bits, errors))

        if len(candidates) != 1:
            return SecdedDecode(None, "uncorrectable")
        data_bits, errors = candidates[0]
        return SecdedDecode(data_bits, "corrected", errors, erasures)


def _xor(values: Iterable[int]) -> int:
    result = 0
    for value in values:
        result ^= value
    return result
