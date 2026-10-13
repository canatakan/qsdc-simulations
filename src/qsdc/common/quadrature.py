from __future__ import annotations

from cmath import phase
from dataclasses import dataclass
from math import pi


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
