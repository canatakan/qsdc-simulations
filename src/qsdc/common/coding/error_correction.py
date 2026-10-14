from __future__ import annotations

from .bits import hamming_distance


def use_odd_parity(offset: int) -> bool:
    return offset % 4 == 0


def parity_encode(data: str, odd: bool = True) -> str:
    return data + str(data.count("1") % 2 ^ odd)


def parity_decode(word: str, odd: bool = True) -> str | None:
    return word[:-1] if word.count("1") % 2 == odd else None


def secded_encode(data: str) -> str:
    d0, d1, d2, d3 = (int(bit) for bit in data)
    word = [d0 ^ d1 ^ d3, d0 ^ d2 ^ d3, d0, d1 ^ d2 ^ d3, d1, d2, d3]
    return "".join(str(bit) for bit in [*word, sum(word) % 2])


CODEWORDS = {
    "0000": secded_encode("0000"),
    "0001": secded_encode("0001"),
    "0010": secded_encode("0010"),
    "0011": secded_encode("0011"),
    "0100": secded_encode("0100"),
    "0101": secded_encode("0101"),
    "0110": secded_encode("0110"),
    "0111": secded_encode("0111"),
    "1000": secded_encode("1000"),
    "1001": secded_encode("1001"),
    "1010": secded_encode("1010"),
    "1011": secded_encode("1011"),
    "1100": secded_encode("1100"),
    "1101": secded_encode("1101"),
    "1110": secded_encode("1110"),
    "1111": secded_encode("1111"),
}


def secded_decode(word: str) -> str | None:
    for data, codeword in CODEWORDS.items():
        if hamming_distance(word, codeword) <= 1:
            return data

    return None
