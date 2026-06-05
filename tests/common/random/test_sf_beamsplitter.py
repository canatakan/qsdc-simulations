import numpy as np
import pytest

from qsdc.common.random.sf_beamsplitter import SFBeamSplitterQRNG


def assert_numpy_state_equal(left, right):
    assert left[0] == right[0]
    assert np.array_equal(left[1], right[1])
    assert left[2:] == right[2:]


def test_sf_beamsplitter_qrng_raw_bits_are_seeded_and_binary():
    left = SFBeamSplitterQRNG(seed=7, batch_size=4)
    right = SFBeamSplitterQRNG(seed=7, batch_size=4)

    left_bits = [left.raw_bit() for _ in range(8)]
    right_bits = [right.raw_bit() for _ in range(8)]

    assert left.name == "sf-bs-qrng"
    assert left_bits == right_bits
    assert set(left_bits) <= {0, 1}


def test_sf_beamsplitter_qrng_preserves_numpy_random_state():
    np.random.seed(123)
    before = np.random.get_state()

    qrng = SFBeamSplitterQRNG(seed=9, batch_size=2)
    qrng.raw_bit()

    after = np.random.get_state()
    assert_numpy_state_equal(after, before)


def test_sf_beamsplitter_qrng_validates_settings():
    with pytest.raises(ValueError, match="batch_size"):
        SFBeamSplitterQRNG(batch_size=0)

    with pytest.raises(ValueError, match="cutoff_dim"):
        SFBeamSplitterQRNG(cutoff_dim=1)
