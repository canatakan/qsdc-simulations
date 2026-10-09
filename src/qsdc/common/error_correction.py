from __future__ import annotations

from itertools import product

from qsdc.common.bits import hamming_distance


def parity_encode(data: str, odd: bool = True) -> str:
    return data + str(data.count("1") % 2 ^ odd)


def parity_decode(word: str, odd: bool = True) -> str | None:
    return word[:-1] if word.count("1") % 2 == odd else None


def secded_encode(data: str) -> str:
    d0, d1, d2, d3 = (int(bit) for bit in data)
    word = [d0 ^ d1 ^ d3, d0 ^ d2 ^ d3, d0, d1 ^ d2 ^ d3, d1, d2, d3]
    return "".join(str(bit) for bit in [*word, sum(word) % 2])


CODEWORDS = {
    secded_encode("".join(data)): "".join(data) for data in product("01", repeat=4)
}


def secded_decode(word: str) -> str | None:
    for codeword, data in CODEWORDS.items():
        if hamming_distance(word, codeword) <= 1:
            return data
    return None
