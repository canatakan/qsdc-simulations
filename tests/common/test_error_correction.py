from itertools import combinations, product

from qsdc.common.error_correction import secded_decode, secded_encode

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
