from __future__ import annotations

from dataclasses import replace
from math import inf, sqrt

from qsdc.common.intervals import (
    BINARY_LABELS,
    GRAY_LABELS,
    GaussianIntervalCode,
    UniformIntervalCode,
)
from qsdc.common.quadrature import VACUUM_VARIANCE

MESSAGE_DIRECTION = 1 + 1j

DEFAULT = UniformIntervalCode(
    BINARY_LABELS, (-inf, -3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0, inf), tail_width=1.0
)
DEFAULT_VARIANCE_SNU = 64 / 3
# Table I of Cao et al. (V_A = 8 SNU), scaled to the default's energy.
CAO_BOUNDS_SNU = (-3.2537, -1.9077, -0.9012, 0.0, 0.9012, 1.9077, 3.2537)
CAO_SCALE = sqrt(DEFAULT_VARIANCE_SNU / 8.0 * VACUUM_VARIANCE)
GAUSSIAN_GRAY = GaussianIntervalCode(
    GRAY_LABELS,
    (-inf, *(bound * CAO_SCALE for bound in CAO_BOUNDS_SNU), inf),
    sigma=sqrt(DEFAULT_VARIANCE_SNU * VACUUM_VARIANCE),
)

INTERVAL_CODES = {
    "default": DEFAULT,
    "gray": replace(DEFAULT, labels=GRAY_LABELS),
    "gaussian_gray": GAUSSIAN_GRAY,
}
