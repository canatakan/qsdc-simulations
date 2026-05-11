"""Backends for ideal and Strawberry Fields protocol simulation."""

from __future__ import annotations

from dataclasses import dataclass
from math import pi
from typing import Protocol
import numpy as np
import strawberryfields as sf
from strawberryfields import ops

from .gaussian import (
    displacement_after_unsqueeze,
    sf_gate_args,
)


class QSDCBackend(Protocol):
    """Minimal backend contract needed by the QSDC protocol."""

    @property
    def name(self) -> str:
        """Backend display name."""
        ...

    def begin_run(self, seed: int) -> None:
        """Reset backend-level randomness for one protocol run."""
        ...

    def control_measurement(
        self, alpha: complex, squeeze_r: float, theta: float, axis: str
    ) -> float:
        """Measure one control quadrature after Alice applies S(-s)."""
        ...

    def returned_measurement(
        self, alpha: complex, squeeze_r: float, theta: float, beta: complex, axis: str
    ) -> float:
        """Measure one returned quadrature after Bob applies S(-s)."""
        ...


@dataclass(frozen=True)
class AnalyticBackend:
    """Formula-only backend following the paper's ideal algebra."""

    name: str = "analytic"

    def begin_run(self, seed: int) -> None:
        pass

    def control_measurement(
        self, alpha: complex, squeeze_r: float, theta: float, axis: str
    ) -> float:
        if axis == "q":
            return alpha.real
        if axis == "p":
            return alpha.imag
        raise ValueError(f"unknown quadrature axis {axis!r}")

    def returned_measurement(
        self, alpha: complex, squeeze_r: float, theta: float, beta: complex, axis: str
    ) -> float:
        returned_alpha = alpha + \
            displacement_after_unsqueeze(beta, squeeze_r, theta)
        if axis == "q":
            return returned_alpha.real
        if axis == "p":
            return returned_alpha.imag
        raise ValueError(f"unknown quadrature axis {axis!r}")


@dataclass(frozen=True)
class StrawberryFieldsBackend:
    """One-mode Gaussian backend using Strawberry Fields measurements."""

    name: str = "strawberryfields"

    def begin_run(self, seed: int) -> None:
        np.random.seed(seed)

    def control_measurement(
        self, alpha: complex, squeeze_r: float, theta: float, axis: str
    ) -> float:
        prog = sf.Program(1)
        alpha_abs, alpha_phase = sf_gate_args(alpha)
        phi = _homodyne_angle(axis)

        with prog.context as q:
            ops.Dgate(alpha_abs, alpha_phase) | q[0]
            # SF's sign convention is opposite to Eq. (5)-(7) in the paper.
            ops.Sgate(-squeeze_r, theta) | q[0]
            ops.Sgate(squeeze_r, theta) | q[0]
            ops.MeasureHomodyne(phi) | q[0]

        eng = sf.Engine("gaussian")
        result = eng.run(prog)
        return float(result.samples[0, 0]) / 2.0

    def returned_measurement(
        self, alpha: complex, squeeze_r: float, theta: float, beta: complex, axis: str
    ) -> float:
        prog = sf.Program(1)
        alpha_abs, alpha_phase = sf_gate_args(alpha)
        beta_abs, beta_phase = sf_gate_args(beta)
        phi = _homodyne_angle(axis)

        with prog.context as q:
            ops.Dgate(alpha_abs, alpha_phase) | q[0]
            # SF's sign convention is opposite to Eq. (5)-(7) in the paper.
            ops.Sgate(-squeeze_r, theta) | q[0]
            if beta != 0:
                ops.Dgate(beta_abs, beta_phase) | q[0]
            ops.Sgate(squeeze_r, theta) | q[0]
            ops.MeasureHomodyne(phi) | q[0]

        eng = sf.Engine("gaussian")
        result = eng.run(prog)
        return float(result.samples[0, 0]) / 2.0


def make_backend(name: str) -> QSDCBackend:
    if name == "analytic":
        return AnalyticBackend()
    if name in {"sf", "strawberryfields"}:
        return StrawberryFieldsBackend()
    raise ValueError(f"unknown backend {name!r}")


def _homodyne_angle(axis: str) -> float:
    if axis == "q":
        return 0.0
    if axis == "p":
        return pi / 2.0
    raise ValueError(f"unknown quadrature axis {axis!r}")
