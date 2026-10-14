from __future__ import annotations

from dataclasses import dataclass
from math import exp, sqrt

from qsdc.common.transmission import SecurityTest

from ..constants import EPR_BOUND
from .backends import Backend


@dataclass(frozen=True)
class Check:
    index: int
    alice: complex
    bob: complex

    @property
    def statistic(self) -> float:
        # Eq. 5: X_m^2 + P_m^2, below 2 for an entangled pair.
        x = (self.alice.real - self.bob.real) / sqrt(2)
        p = (self.alice.imag + self.bob.imag) / sqrt(2)

        return x * x + p * p

    @property
    def passed(self) -> bool:
        return self.statistic < EPR_BOUND


class Checks:
    def __init__(self, backend: Backend, tolerance_sigmas: float):
        self.backend = backend
        self.tolerance_sigmas = tolerance_sigmas

        # Bob calibrates the checks to the honest channel he expects.
        sigma = backend.check_sigma()
        self.expected_failure_rate = exp(-EPR_BOUND / (2 * sigma**2))

    def measure(self, positions: list[int]) -> tuple[Check, ...]:
        checks = []
        for index in positions:
            alice, bob = self.backend.measure_check()
            checks.append(Check(index, alice, bob))

        return tuple(checks)

    def judge(self, checks: list[Check]) -> SecurityTest:
        return SecurityTest.judge(
            checks, self.expected_failure_rate, self.tolerance_sigmas
        )
