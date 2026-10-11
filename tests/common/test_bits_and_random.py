import numpy as np
import pytest

from qsdc.common.bits import bits_to_bytes, bytes_to_bits
from qsdc.common.random import make_random_source, weighted_random_bits


def test_bytes_round_trip_through_bits():
    assert bytes_to_bits(b"\x05") == "00000101"
    assert bits_to_bytes(bytes_to_bits("QSDC ✓".encode())) == "QSDC ✓".encode()


def test_weighted_bits_follow_the_one_probability():
    rng = make_random_source("classical", 1)
    assert weighted_random_bits(8, 0.0, rng) == "0" * 8
    assert weighted_random_bits(8, 1.0, rng) == "1" * 8
    assert weighted_random_bits(4000, 0.25, rng).count("1") / 4000 == pytest.approx(
        0.25, abs=0.02
    )


def test_random_sources_are_reproducible_from_their_seed():
    for name in ("classical", "sf-bs-qrng"):
        left, right = make_random_source(name, 7), make_random_source(name, 7)
        draws = [
            (source.uniform(-1, 1), source.choice("qp"), source.shuffled(range(6)))
            for source in (left, right)
        ]
        assert draws[0] == draws[1]


def test_quantum_random_source_leaves_numpy_randomness_untouched():
    np.random.seed(123)
    expected = np.random.random()
    np.random.seed(123)
    make_random_source("sf-bs-qrng", 9).uniform(0, 1)
    assert np.random.random() == expected
