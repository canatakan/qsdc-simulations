"""Gaussian-state algebra used by the paper's QSDC protocol."""

from __future__ import annotations

from cmath import exp, phase
from math import cosh, sinh


def squeeze_displace_forward(alpha: complex, squeeze_r: float, theta: float) -> complex:
    """Compute beta in S(s)D(alpha) = D(beta)S(s)."""

    return alpha * cosh(squeeze_r) + exp(1j * theta) * alpha.conjugate() * sinh(
        squeeze_r
    )


def squeeze_displace_inverse(beta: complex, squeeze_r: float, theta: float) -> complex:
    """Recover alpha from beta using Eq. (7) of the paper."""

    return beta * cosh(squeeze_r) - exp(1j * theta) * beta.conjugate() * sinh(
        squeeze_r
    )


def displacement_after_unsqueeze(
    beta: complex, squeeze_r: float, theta: float
) -> complex:
    """Alice's beta as seen after Bob applies S(-s)."""

    return squeeze_displace_inverse(beta, squeeze_r, theta)


def recover_alice_displacement(
    delta: complex, squeeze_r: float, theta: float
) -> complex:
    """Recover Alice's beta from Bob's observed delta."""

    return squeeze_displace_forward(delta, squeeze_r, theta)


def sf_gate_args(alpha: complex) -> tuple[float, float]:
    """Convert a complex amplitude to Strawberry Fields polar gate arguments."""

    if alpha == 0:
        return 0.0, 0.0
    return abs(alpha), phase(alpha)


def quadrature_means_to_alpha(x_mean: float, p_mean: float) -> complex:
    """Convert Strawberry Fields means to the paper's alpha convention."""

    return complex(x_mean / 2.0, p_mean / 2.0)


def alpha_to_quadrature_means(alpha: complex) -> tuple[float, float]:
    """Convert a complex amplitude to Strawberry Fields quadrature means."""

    return 2.0 * alpha.real, 2.0 * alpha.imag
