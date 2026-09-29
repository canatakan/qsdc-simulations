"""Extended Hamming (8, 4) code: corrects one error and detects two per codeword."""

from __future__ import annotations

from itertools import product

from qsdc.common.bits import hamming_distance


def secded_encode(data: str) -> str:
    d0, d1, d2, d3 = (int(bit) for bit in data)
    word = [d0 ^ d1 ^ d3, d0 ^ d2 ^ d3, d0, d1 ^ d2 ^ d3, d1, d2, d3]
    return "".join(str(bit) for bit in [*word, sum(word) % 2])


CODEWORDS = {
    secded_encode("".join(data)): "".join(data) for data in product("01", repeat=4)
}


def secded_decode(word: str) -> str | None:
    """Return the data bits of the codeword within distance one, or None if there is none."""
    for codeword, data in CODEWORDS.items():
        if hamming_distance(word, codeword) <= 1:
            return data
    return None
