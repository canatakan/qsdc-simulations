from math import isclose

from qsdc.protocols.cao.simulator.encoding import gaussian_encoding


def test_gaussian_encoding_covers_expected_symbols():
    encoding = gaussian_encoding(box_bit_length=3, variance=4.0)
    intervals = encoding.intervals

    assert len(intervals) == 8
    assert intervals[0].bits == "000"
    assert intervals[-1].bits == "111"
    assert intervals[0].lower == float("-inf")
    assert intervals[-1].upper == float("inf")
    assert isclose(intervals[3].upper, 0.0)
