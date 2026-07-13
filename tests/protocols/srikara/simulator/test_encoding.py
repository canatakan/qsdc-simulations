from qsdc.common.bits import chunk_bits
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


def test_default_intervals_round_trip_padded_bitstream():
    rng = ClassicalRandomSource(2)
    symbols = chunk_bits("0100111001", 3)
    values = [sample_message_value(bits, rng) for bits in symbols]

    assert symbols == ("010", "011", "100", "100")
    assert "".join(bits_for_real(value) for value in values) == "010011100100"


def test_boundaries_decode_to_right_interval():
    assert bits_for_real(-3.0) == "001"
    assert bits_for_real(-2.0) == "010"
    assert bits_for_real(-1.0) == "011"
    assert bits_for_real(0.0) == "100"
    assert bits_for_real(1.0) == "101"
    assert bits_for_real(2.0) == "110"
    assert bits_for_real(3.0) == "111"


def test_optimized_interval_round_trip_samples():
    rng = ClassicalRandomSource(1)
    for bits in ("000", "001", "010", "011", "100", "101", "110", "111"):
        value = sample_message_value(bits, rng, intervals="optimized")
        assert interval_for_bits(bits, intervals="optimized").contains(value)
        assert bits_for_real(value, intervals="optimized") == bits
