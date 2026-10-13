import numpy as np
import pytest

from qsdc.common.coding.universal_hash import UniversalHash


def random_bits(length, rng):
    return "".join(rng.choice(["0", "1"], length))


def test_preimage_hashes_to_the_output():
    rng = np.random.default_rng(1)
    hashing = UniversalHash(64, 20, seed=2)
    for _ in range(10):
        output = random_bits(20, rng)
        payload = hashing.preimage(output, random_bits(hashing.free_bits, rng))

        assert len(payload) == 64
        assert hashing.hash(payload) == output


def test_rows_describe_the_hash():
    rng = np.random.default_rng(3)
    hashing = UniversalHash(40, 12, seed=4)
    payload = random_bits(40, rng)

    by_rows = "".join(
        str(sum(int(payload[i]) for i in row) % 2) for row in hashing.rows()
    )

    assert by_rows == hashing.hash(payload)


def test_rejects_an_output_longer_than_the_input():
    with pytest.raises(ValueError):
        UniversalHash(10, 11, seed=0)
