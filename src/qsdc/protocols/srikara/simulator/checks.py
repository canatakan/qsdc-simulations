from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from math import erfc, sqrt

from qsdc.common.quadrature import P, Q, Quadrature
from qsdc.common.random import RandomSource
from qsdc.common.transmission import SecurityTest

from .backends import Backend, Expectation, PreparedState

AXES = (Q, P)


@dataclass(frozen=True)
class Check:
    index: int
    axis: Quadrature
    expected: float
    sigma: float
    measured: float
    passed: bool

    @classmethod
    def compare(
        cls,
        state: PreparedState,
        axis: Quadrature,
        expected: Expectation,
        measured: float,
        tolerance_sigmas: float,
    ) -> Check:
        # A check passes within tolerance_sigmas of its expected value.
        passed = abs(measured - expected.mean) <= tolerance_sigmas * expected.sigma
        return cls(state.index, axis, expected.mean, expected.sigma, measured, passed)


class Checks:
    def __init__(self, backend: Backend, tolerance_sigmas: float):
        self.backend = backend
        self.tolerance_sigmas = tolerance_sigmas

    def controls(
        self,
        states: tuple[PreparedState, ...],
        indices: tuple[int, ...],
        rng: RandomSource,
    ) -> tuple[Check, ...]:
        # Alice unsqueezes each control and measures q or p at random.
        backend = self.backend
        return self.measure(
            states, indices, rng, backend.expect_control, backend.measure_control
        )

    def decoys(
        self,
        states: tuple[PreparedState, ...],
        indices: tuple[int, ...],
        rng: RandomSource,
    ) -> tuple[Check, ...]:
        # Bob unsqueezes each decoy and measures q or p at random.
        backend = self.backend
        return self.measure(
            states, indices, rng, backend.expect_returned, backend.measure_returned
        )

    def measure(
        self,
        states: tuple[PreparedState, ...],
        indices: tuple[int, ...],
        rng: RandomSource,
        expect: Callable[[PreparedState, Quadrature], Expectation],
        measure: Callable[[PreparedState, Quadrature], float],
    ) -> tuple[Check, ...]:
        checks = []
        for i in indices:
            state, axis = states[i], rng.choice(AXES)
            expected, measured = expect(state, axis), measure(state, axis)
            checks.append(
                Check.compare(state, axis, expected, measured, self.tolerance_sigmas)
            )

        return tuple(checks)

    def judge(self, checks: tuple[Check, ...]) -> SecurityTest:
        # An honest check fails with probability erfc(k / sqrt 2) at k sigmas.
        k = self.tolerance_sigmas
        return SecurityTest.judge(checks, erfc(k / sqrt(2)), k)
