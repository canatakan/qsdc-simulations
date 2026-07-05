from qsdc.common.random.classical import ClassicalRandomSource
from qsdc.protocols.srikara.simulator.encoding import (
    bits_for_real,
    interval_for_bits,
    sample_message_value,
)


def test_interval_round_trip_samples():
    rng = ClassicalRandomSource(1)
    for bits in ("000", "001", "010", "011", "100", "101", "110", "111"):
        value = sample_message_value(bits, rng)
        assert bits_for_real(value) == bits


def test_boundaries_decode_to_right_interval():
    assert bits_for_real(-3.0) == "001"
    assert bits_for_real(-2.0) == "010"
    assert bits_for_real(-1.0) == "011"
    assert bits_for_real(0.0) == "100"
    assert bits_for_real(1.0) == "101"
    assert bits_for_real(2.0) == "110"
    assert bits_for_real(3.0) == "111"


def test_optimized_intervals_match_table_values():
    intervals = [
        interval_for_bits(bits, intervals="optimized")
        for bits in ("000", "001", "011", "010", "110", "100", "101", "111")
    ]

    assert [interval.bits for interval in intervals] == [
        "000",
        "001",
        "011",
        "010",
        "110",
        "100",
        "101",
        "111",
    ]
    assert [(interval.lower, interval.upper) for interval in intervals] == [
        (float("-inf"), -3.25),
        (-3.25, -1.91),
        (-1.91, -0.90),
        (-0.90, 0.0),
        (0.0, 0.90),
        (0.90, 1.91),
        (1.91, 3.25),
        (3.25, float("inf")),
    ]
    for left, right in zip(intervals, intervals[1:]):
        assert _hamming_distance(left.bits, right.bits) == 1


def test_optimized_interval_round_trip_samples():
    rng = ClassicalRandomSource(1)
    for bits in ("000", "001", "010", "011", "100", "101", "110", "111"):
        value = sample_message_value(bits, rng, intervals="optimized")
        assert interval_for_bits(bits, intervals="optimized").contains(value)
        assert bits_for_real(value, intervals="optimized") == bits


def _hamming_distance(left: str, right: str) -> int:
    return sum(left_bit != right_bit for left_bit, right_bit in zip(left, right))
