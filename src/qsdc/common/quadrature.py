"""Shared continuous-variable quadrature definitions."""

from enum import Enum
from math import pi


class QuadratureAxis(str, Enum):
    Q = "q"
    P = "p"

    def component(self, value: complex) -> float:
        return value.real if self is QuadratureAxis.Q else value.imag

    @property
    def angle(self) -> float:
        return 0.0 if self is QuadratureAxis.Q else pi / 2.0
