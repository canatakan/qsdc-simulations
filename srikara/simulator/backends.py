"""Backends for ideal and Strawberry Fields protocol simulation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import strawberryfields as sf
from strawberryfields import ops

from .gaussian import (
    displacement_after_unsqueeze,
    quadrature_means_to_alpha,
    sf_gate_args,
)


class QSDCBackend(Protocol):
    """Minimal backend contract needed by the QSDC protocol."""

    @property
    def name(self) -> str:
        """Backend display name."""
        ...

    def control_amplitude(
        self, alpha: complex, squeeze_r: float, theta: float
    ) -> complex:
        """Return Alice's amplitude after applying S(-s) to a control state."""
        ...

    def returned_amplitude(
        self, alpha: complex, squeeze_r: float, theta: float, beta: complex
    ) -> complex:
        """Return Bob's amplitude after Alice's D(beta) and Bob's S(-s)."""
        ...


@dataclass(frozen=True)
class AnalyticBackend:
    """Formula-only backend following the paper's ideal algebra."""

    name: str = "analytic"

    def control_amplitude(
        self, alpha: complex, squeeze_r: float, theta: float
    ) -> complex:
        return alpha

    def returned_amplitude(
        self, alpha: complex, squeeze_r: float, theta: float, beta: complex
    ) -> complex:
        return alpha + displacement_after_unsqueeze(beta, squeeze_r, theta)


@dataclass(frozen=True)
class StrawberryFieldsBackend:
    """One-mode Gaussian backend using Strawberry Fields native operations."""

    name: str = "strawberryfields"

    def control_amplitude(
        self, alpha: complex, squeeze_r: float, theta: float
    ) -> complex:
        prog = sf.Program(1)
        alpha_abs, alpha_phase = sf_gate_args(alpha)

        with prog.context as q:
            ops.Dgate(alpha_abs, alpha_phase) | q[0]
            # SF's sign convention is opposite to Eq. (5)-(7) in the paper.
            ops.Sgate(-squeeze_r, theta) | q[0]
            ops.Sgate(squeeze_r, theta) | q[0]

        eng = sf.Engine("gaussian")
        result = eng.run(prog)
        x_mean, p_mean = result.state.means()
        return quadrature_means_to_alpha(float(x_mean), float(p_mean))

    def returned_amplitude(
        self, alpha: complex, squeeze_r: float, theta: float, beta: complex
    ) -> complex:
        prog = sf.Program(1)
        alpha_abs, alpha_phase = sf_gate_args(alpha)
        beta_abs, beta_phase = sf_gate_args(beta)

        with prog.context as q:
            ops.Dgate(alpha_abs, alpha_phase) | q[0]
            # SF's sign convention is opposite to Eq. (5)-(7) in the paper.
            ops.Sgate(-squeeze_r, theta) | q[0]
            if beta != 0:
                ops.Dgate(beta_abs, beta_phase) | q[0]
            ops.Sgate(squeeze_r, theta) | q[0]

        eng = sf.Engine("gaussian")
        result = eng.run(prog)
        x_mean, p_mean = result.state.means()
        return quadrature_means_to_alpha(float(x_mean), float(p_mean))


def make_backend(name: str) -> QSDCBackend:
    if name == "analytic":
        return AnalyticBackend()
    if name in {"sf", "strawberryfields"}:
        return StrawberryFieldsBackend()
    raise ValueError(f"unknown backend {name!r}")
