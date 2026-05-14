from simulator.core.encoding import bits_for_real, sample_message_value
from simulator.core.random_source import IdealQRNG


def test_interval_round_trip_samples():
    rng = IdealQRNG(1)
    for bits in ("000", "001", "010", "011", "100", "101", "110", "111"):
        value = sample_message_value(bits, rng)
        assert bits_for_real(value) == bits
