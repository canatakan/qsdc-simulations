from __future__ import annotations

from dataclasses import replace
from math import sqrt

from qsdc.common.coding.intervals import (
    BINARY_LABELS,
    GRAY_LABELS,
    GaussianIntervalCode,
    UniformIntervalCode,
)

from ..constants import (
    MESSAGE_BOUNDS,
    MESSAGE_VARIANCE_SNU,
    TAIL_WIDTH,
    VACUUM_VARIANCE,
)

DEFAULT = UniformIntervalCode(BINARY_LABELS, MESSAGE_BOUNDS, tail_width=TAIL_WIDTH)

INTERVAL_CODES = {
    "default": DEFAULT,
    "gray": replace(DEFAULT, labels=GRAY_LABELS),
    "gaussian_gray": GaussianIntervalCode.equiprobable(
        GRAY_LABELS, sqrt(MESSAGE_VARIANCE_SNU * VACUUM_VARIANCE)
    ),
}
