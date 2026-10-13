from math import sqrt

import numpy as np
import pytest

from qsdc.common.random import ClassicalRandomSource
from qsdc.protocols.cao.config import SimulatorConfig
from qsdc.protocols.cao.simulator.mapping import Box, interval_code
from qsdc.protocols.cao.simulator.postprocessing import (
    Estimate,
    confidences,
    reconciliation_code,
)


def test_estimate_recovers_the_gain_and_the_noise():
    rng = np.random.default_rng(1)
    g2 = rng.normal(0, sqrt(8), 20_000)
    measured = 0.6 * g2 + rng.normal(0, 0.3, g2.size)

    result = Estimate.fit(g2, measured)

    assert result.gain == pytest.approx(0.6, rel=0.01)
    assert result.noise_variance == pytest.approx(0.09, rel=0.05)


def test_confidences_follow_the_value_and_the_announced_detection_bits():
    config = SimulatorConfig()
    code = interval_code(config)
    box = Box.map("10", 1, ClassicalRandomSource(2))
    lower, upper = code.interval(box.bits)
    centre = (lower + upper) / 2 if upper < 10 else lower + 0.5

    result = confidences([box], [centre], code, Estimate(1.0, 0.01))

    assert [value < 0 for value in result] == [bit == "1" for bit in box.payload]


def test_box_parities_are_part_of_the_reconciliation_code():
    config = SimulatorConfig()

    code = reconciliation_code(config)

    box_rows = code.rows[-config.boxes :]
    assert box_rows[0] == (0, 1) and box_rows[-1] == (
        config.payload_bits - 2,
        config.payload_bits - 1,
    )
