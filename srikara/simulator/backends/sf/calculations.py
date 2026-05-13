"""Shared Strawberry Fields circuit helpers."""

from __future__ import annotations

from cmath import phase
from math import pi, sqrt

import numpy as np
import strawberryfields as sf
from strawberryfields import ops

from simulator.core.config import validate_sampled_repetitions
from simulator.core.encoding import beta_for_message_value


def homodyne_angle(axis: str) -> float:
    if axis == "q":
        return 0.0
    if axis == "p":
        return pi / 2.0
    raise ValueError(f"unknown quadrature axis {axis!r}")


def homodyne_component_std() -> float:
    return sqrt(sf.hbar / 2.0) / 2.0


def sf_gate_args(alpha: complex) -> tuple[float, float]:
    if alpha == 0:
        return 0.0, 0.0
    return abs(alpha), phase(alpha)


def component_from_means(x_mean: float, p_mean: float, axis: str) -> float:
    if axis == "q":
        return x_mean / 2.0
    if axis == "p":
        return p_mean / 2.0
    raise ValueError(f"unknown quadrature axis {axis!r}")


def build_returned_program(
    alpha: complex, squeeze_r: float, theta: float, beta: complex
) -> sf.Program:
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

    return prog


def build_control_program(alpha: complex, squeeze_r: float, theta: float) -> sf.Program:
    return build_returned_program(alpha, squeeze_r, theta, beta=0j)


def message_unit_beta() -> complex:
    return beta_for_message_value(1.0)


def mean_component(prog: sf.Program, axis: str) -> float:
    result = sf.Engine("gaussian").run(prog)
    x_mean, p_mean = result.state.means()
    return component_from_means(float(x_mean), float(p_mean), axis)


def homodyne_mean(build_program, args: tuple, axis: str, repetitions: int) -> float:
    validate_sampled_repetitions(repetitions)
    samples = [homodyne_sample(build_program(*args), axis) for _ in range(repetitions)]
    return float(np.mean(samples))


def homodyne_sample(prog: sf.Program, axis: str) -> float:
    with prog.context as q:
        ops.MeasureHomodyne(homodyne_angle(axis)) | q[0]

    result = sf.Engine("gaussian").run(prog)
    return float(result.samples[0, 0]) / 2.0
