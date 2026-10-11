from __future__ import annotations

from math import inf

# q = Re alpha, so one shot-noise unit (SNU) of variance is 1/4.
VACUUM_VARIANCE = 0.25
STATES_PER_SYMBOL = 4
MESSAGE_DIRECTION = 1 + 1j
MESSAGE_BOUNDS = (-inf, -3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0, inf)
TAIL_WIDTH = 1.0
MESSAGE_VARIANCE_SNU = 64 / 3
