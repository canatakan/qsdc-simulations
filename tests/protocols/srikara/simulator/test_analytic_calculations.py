from math import isclose

from qsdc.protocols.srikara.simulator.backends.analytic.calculations import (
    displacement_after_unsqueeze,
    recover_alice_displacement,
    squeeze_displace_forward,
    squeeze_displace_inverse,
)


def assert_complex_close(left, right, tol=1e-10):
    assert isclose(left.real, right.real, abs_tol=tol)
    assert isclose(left.imag, right.imag, abs_tol=tol)


def test_squeeze_displace_equations_are_inverses():
    alpha = 0.7 - 1.2j
    squeeze_r = 0.43
    theta = 0.9

    beta = squeeze_displace_forward(alpha, squeeze_r, theta)
    recovered = squeeze_displace_inverse(beta, squeeze_r, theta)

    assert_complex_close(recovered, alpha)


def test_alice_displacement_recovery_after_unsqueeze():
    beta = -1.4 - 1.4j
    squeeze_r = 0.31
    theta = 1.7

    observed_delta = displacement_after_unsqueeze(beta, squeeze_r, theta)
    recovered_beta = recover_alice_displacement(observed_delta, squeeze_r, theta)

    assert_complex_close(recovered_beta, beta)
