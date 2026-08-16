"""Shared Strawberry Fields circuit helpers."""

from __future__ import annotations

from cmath import polar
from math import sqrt

from strawberryfields import Engine, Program, hbar, ops

from qsdc.common.quadrature import QuadratureAxis


def normalize_quadrature(value: float) -> float:
    return value / sqrt(2.0 * hbar)


def normalize_quadrature_variance(variance: float) -> float:
    return variance / (2.0 * hbar)


def build_program(
    alpha: complex, squeeze_r: float, theta: float, beta: complex
) -> Program:
    prog = Program(1)
    alpha_abs, alpha_phase = polar(alpha)
    beta_abs, beta_phase = polar(beta)

    with prog.context as q:
        ops.Dgate(alpha_abs, alpha_phase) | q[0]
        # SF's sign convention is opposite to Eq. (5)-(7) in the paper.
        ops.Sgate(-squeeze_r, theta) | q[0]
        ops.Dgate(beta_abs, beta_phase) | q[0]
        ops.Sgate(squeeze_r, theta) | q[0]

    return prog


def quadrature_mean(prog: Program, axis: QuadratureAxis) -> float:
    result = Engine("gaussian").run(prog)
    state = result.state

    if state is None:
        raise RuntimeError("Strawberry Fields execution returned no state")

    mean, _ = state.quad_expectation(0, axis.angle)
    return normalize_quadrature(float(mean))


def homodyne_sample(prog: Program, axis: QuadratureAxis) -> float:
    with prog.context as q:
        ops.MeasureHomodyne(axis.angle) | q[0]

    result = Engine("gaussian").run(prog)
    return normalize_quadrature(float(result.samples[0, 0]))
