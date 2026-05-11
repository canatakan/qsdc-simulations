from random import Random

from simulator.encoding import bits_for_real, sample_message_value


def test_interval_round_trip_samples():
    rng = Random(1)
    for bits in ("000", "001", "010", "011", "100", "101", "110", "111"):
        value = sample_message_value(bits, rng)
        assert bits_for_real(value) == bits
