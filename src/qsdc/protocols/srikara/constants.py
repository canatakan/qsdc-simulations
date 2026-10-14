from __future__ import annotations

from dataclasses import replace
from math import inf, sqrt

from qsdc.common.coding.intervals import (
    BINARY_LABELS,
    GRAY_LABELS,
    GaussianIntervalCode,
    UniformIntervalCode,
)

VACUUM_VARIANCE = 0.25
STATES_PER_SYMBOL = 4
MESSAGE_DIRECTION = 1 + 1j
MESSAGE_BOUNDS = (-inf, -3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0, inf)
TAIL_WIDTH = 1.0
MESSAGE_VARIANCE_SNU = 64 / 3

DEFAULT = UniformIntervalCode(BINARY_LABELS, MESSAGE_BOUNDS, tail_width=TAIL_WIDTH)

INTERVAL_CODES = {
    "default": DEFAULT,
    "gray": replace(DEFAULT, labels=GRAY_LABELS),
    "gaussian_gray": GaussianIntervalCode.equiprobable(
        GRAY_LABELS, sqrt(MESSAGE_VARIANCE_SNU * VACUUM_VARIANCE)
    ),
}
