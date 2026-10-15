from math import log

import numpy as np
import pytest

from qsdc.common.coding.ldpc import LdpcCode


def flipped(bits, probability, rng):
    return "".join(str(int(bit) ^ int(rng.random() < probability)) for bit in bits)


def confidences(bits, probability):
    weight = log((1 - probability) / probability)
    return [-weight if bit == "1" else weight for bit in bits]


def random_bits(length, rng):
    return "".join(rng.choice(["0", "1"], length))


def test_syndrome_is_the_parity_of_each_row():
    code = LdpcCode(4, [[0, 1], [1, 2, 3]])

    assert code.syndrome("1100") == "01"
    assert code.syndrome("1011") == "10"


def test_regular_code_has_the_requested_shape():
    code = LdpcCode.regular(600, 300, 3, seed=1)

    assert code.length == 600
    assert 0 < code.checks <= 300
    assert sum(len(row) for row in code.rows) <= 3 * 600


@pytest.mark.parametrize("probability", [0.02, 0.05])
def test_decoding_recovers_the_bits_behind_a_syndrome(probability):
    rng = np.random.default_rng(2)
    code = LdpcCode.regular(1024, 512, 3, seed=3)
    for _ in range(5):
        bits = random_bits(1024, rng)
        noisy = flipped(bits, probability, rng)

        assert code.decode(confidences(noisy, probability), code.syndrome(bits)) == bits


def test_decoding_reports_failure_when_the_syndrome_is_too_short():
    rng = np.random.default_rng(4)
    code = LdpcCode.regular(1024, 100, 3, seed=5)
    bits = random_bits(1024, rng)
    noisy = flipped(bits, 0.2, rng)

    assert code.decode(confidences(noisy, 0.2), code.syndrome(bits), 30) is None


def test_extra_rows_take_part_in_decoding():
    code = LdpcCode(2, []).extended([[0, 1]])

    assert code.decode([5.0, -0.5], "0") == "00"
    assert code.decode([5.0, -0.5], "1") == "01"


@pytest.mark.parametrize("data_bits,parity_bits", [(12, 9), (96, 96), (192, 96)])
def test_transmitted_codewords_are_systematic_and_satisfy_every_check(
    data_bits,
    parity_bits,
):
    code = LdpcCode.systematic(data_bits, parity_bits, seed=3)
    rng = np.random.default_rng(4)
    for _ in range(10):
        bits = random_bits(data_bits, rng)
        word = code.encode(bits)

        assert len(word) == data_bits + parity_bits
        assert word[:data_bits] == bits
        assert code.syndrome(word) == "0" * parity_bits

    assert code.rows == LdpcCode.systematic(data_bits, parity_bits, seed=3).rows
    assert code.rows != LdpcCode.systematic(data_bits, parity_bits, seed=4).rows


def test_transmitted_code_corrects_each_single_bit_error_in_a_default_block():
    code = LdpcCode.systematic(96, 96)
    word = code.encode(random_bits(96, np.random.default_rng(3)))
    for i in range(code.length):
        prior = confidences(word, 0.01)
        prior[i] *= -1

        assert code.decode(prior, "0" * code.checks) == word


@pytest.mark.parametrize("shape", [(0, 6, 3), (6, 0, 3), (6, 3, 4), (6, 3, 0)])
def test_transmitted_code_rejects_invalid_shapes(shape):
    with pytest.raises(ValueError):
        LdpcCode.systematic(*shape)


@pytest.mark.parametrize("bits", ["101", "0" * 95 + "x"])
def test_transmitted_code_rejects_invalid_data(bits):
    with pytest.raises(ValueError):
        LdpcCode.systematic(96, 96).encode(bits)


def test_reconciliation_code_rejects_codeword_encoding():
    code = LdpcCode.regular(96, 48, 3, seed=0)

    with pytest.raises(ValueError, match="encoding requires a systematic code"):
        code.encode("0" * 48)
