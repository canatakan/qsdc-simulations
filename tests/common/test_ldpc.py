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
