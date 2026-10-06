"""The quadrature a homodyne detector measures, set by the phase of its local oscillator."""

from __future__ import annotations

from cmath import phase
from dataclasses import dataclass
from math import pi

# Quadratures are measured in units where the vacuum variance is 1/4 (q = Re alpha), so one
# shot-noise unit (SNU) of variance is 1/4.
VACUUM_VARIANCE = 0.25


@dataclass(frozen=True)
class Quadrature:
    direction: complex

    def component(self, value: complex) -> float:
        d = self.direction
        return (value.real * d.real + value.imag * d.imag) / abs(d)

    @property
    def angle(self) -> float:
        return phase(self.direction)

    @property
    def name(self) -> str:
        return {1: "q", 1j: "p"}.get(self.direction, f"{self.angle / pi:+.3f}π")


Q = Quadrature(1 + 0j)
P = Quadrature(1j)
