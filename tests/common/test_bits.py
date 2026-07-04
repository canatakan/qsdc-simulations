import pytest

from qsdc.common.bits import (
    bits_to_bytes,
    bytes_to_bits,
    chunk_bits,
    hamming_distance,
    weighted_random_bits,
)
from qsdc.common.random.classical import ClassicalRandomSource


def test_hamming_distance_counts_different_positions():
    assert hamming_distance("0011", "1010") == 2


def test_hamming_distance_accepts_empty_bitstreams():
    assert hamming_distance("", "") == 0


def test_hamming_distance_requires_equal_lengths():
    with pytest.raises(ValueError, match="equal length"):
        hamming_distance("001", "0011")


def test_bytes_to_bits_uses_eight_bits_per_byte():
    assert bytes_to_bits(b"\x00\x05\xff") == "000000000000010111111111"


def test_bits_to_bytes_round_trips_byte_aligned_bits():
    payload = b"QSDC"

    assert bits_to_bytes(bytes_to_bits(payload)) == payload


def test_bits_to_bytes_rejects_non_byte_aligned_bitstreams():
    with pytest.raises(ValueError, match="byte-aligned"):
        bits_to_bytes("101")


def test_chunk_bits_splits_exact_widths_without_padding():
    assert chunk_bits("001101", 3) == ("001", "101")


def test_chunk_bits_pads_incomplete_final_chunk():
    assert chunk_bits("10101", 3) == ("101", "010")


def test_chunk_bits_allows_custom_padding_bit():
    assert chunk_bits("10101", 3, pad="1") == ("101", "011")


def test_chunk_bits_requires_positive_width():
    with pytest.raises(ValueError, match="width"):
        chunk_bits("101", 0)


def test_weighted_random_bits_respects_extreme_probabilities():
    assert weighted_random_bits(6, 0.0, ClassicalRandomSource(1)) == "000000"
    assert weighted_random_bits(6, 1.0, ClassicalRandomSource(1)) == "111111"


def test_weighted_random_bits_is_reproducible_for_seeded_source():
    left = weighted_random_bits(16, 0.35, ClassicalRandomSource(12))
    right = weighted_random_bits(16, 0.35, ClassicalRandomSource(12))

    assert left == right
    assert set(left) <= {"0", "1"}
