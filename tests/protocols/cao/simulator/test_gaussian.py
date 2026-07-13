from math import isclose

from qsdc.common.random.classical import ClassicalRandomSource
from qsdc.protocols.cao.simulator.gaussian import (
    equal_probability_intervals,
    interval_for_symbol,
    sample_from_interval,
    symbol_for_value,
)


def test_equal_probability_intervals_cover_expected_symbols():
    intervals = equal_probability_intervals(box_bit_length=3, variance=4.0)

    assert len(intervals) == 8
    assert intervals[0].symbol == "000"
    assert intervals[-1].symbol == "111"
    assert intervals[0].lower == float("-inf")
    assert intervals[-1].upper == float("inf")
    assert isclose(intervals[3].probability_upper, 0.5)


def test_sample_from_interval_decodes_to_same_symbol():
    intervals = equal_probability_intervals(box_bit_length=3, variance=4.0)
    interval = interval_for_symbol("101", intervals)

    value = sample_from_interval(interval, 4.0, ClassicalRandomSource(5))

    assert symbol_for_value(value, intervals) == "101"
