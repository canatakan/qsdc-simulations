"""Analytic backend calculations."""

from __future__ import annotations

from cmath import exp
from math import cosh, sinh


def squeeze_displace_forward(
    alpha: complex, squeeze_r: float, theta: float
) -> complex:
    """Compute beta in the identity S(s)D(alpha) = D(beta)S(s).

    Formula:
        s = r exp(i theta)
        beta = alpha cosh(r) + exp(i theta) alpha* sinh(r)
    """

    return alpha * cosh(squeeze_r) + exp(1j * theta) * alpha.conjugate() * sinh(
        squeeze_r
    )


def squeeze_displace_inverse(
    beta: complex, squeeze_r: float, theta: float
) -> complex:
    """Recover alpha from beta by inverting S(s)D(alpha) = D(beta)S(s).

    Formula:
        s = r exp(i theta)
        alpha = beta cosh(r) - exp(i theta) beta* sinh(r)
    """

    return beta * cosh(squeeze_r) - exp(1j * theta) * beta.conjugate() * sinh(
        squeeze_r
    )


def displacement_after_unsqueeze(
    beta: complex, squeeze_r: float, theta: float
) -> complex:
    """Compute Alice's displacement as seen after Bob applies S(-s).

    Protocol situation:
        Alice applies D(beta_A) to a message state.
        Bob later applies S†(s) = S(-s).

    Formula:
        Delta = beta_A cosh(r) - exp(i theta) beta_A* sinh(r),
          where beta_A is Alice's displacement: beta_A = m_A(1 + i)
    """

    return squeeze_displace_inverse(beta, squeeze_r, theta)


def recover_alice_displacement(
    delta: complex, squeeze_r: float, theta: float
) -> complex:
    """Recover Alice's beta_A from Bob's observed displacement shift.

    Formula:
        beta_A = Delta cosh(r) + exp(i theta) Delta* sinh(r)
    """

    return squeeze_displace_forward(delta, squeeze_r, theta)
