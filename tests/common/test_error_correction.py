from itertools import combinations, product

import pytest

from qsdc.common.coding.error_correction import (
    parity_decode,
    parity_encode,
    secded_decode,
    secded_encode,
)

DATA = ["".join(bits) for bits in product("01", repeat=4)]


def flip(word, *positions):
    return "".join(
        str(1 - int(bit)) if i in positions else bit for i, bit in enumerate(word)
    )


def test_secded_corrects_every_single_bit_error():
    for data in DATA:
        codeword = secded_encode(data)
        assert secded_decode(codeword) == data
        assert all(secded_decode(flip(codeword, i)) == data for i in range(8))


def test_secded_detects_every_double_bit_error():
    for data in DATA:
        codeword = secded_encode(data)
        assert all(
            secded_decode(flip(codeword, *pair)) is None
            for pair in combinations(range(8), 2)
        )


@pytest.mark.parametrize("odd", [True, False])
def test_parity_detects_every_single_bit_error(odd):
    for data in ("".join(bits) for bits in product("01", repeat=2)):
        word = parity_encode(data, odd)
        assert word.count("1") % 2 == odd
        assert parity_decode(word, odd) == data
        assert all(parity_decode(flip(word, i), odd) is None for i in range(3))
