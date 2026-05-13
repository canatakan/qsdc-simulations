"""Print a hand-checkable one-symbol CV QSDC calculation."""

from __future__ import annotations

from simulator.backends.analytic.calculations import (
    displacement_after_unsqueeze,
    recover_message_displacement,
    squeeze_displace_forward,
    squeeze_displace_inverse,
)
from simulator.core.encoding import beta_for_message_value, bits_for_real


def main() -> None:
    alpha = 2.0 + 3.0j
    squeeze_r = 0.0
    theta = 0.0
    bits = "110"
    message_value = 2.5
    message_beta = beta_for_message_value(message_value)

    print_header("1. Fixed inputs")
    print(f"alpha = {fmt(alpha)}")
    print(f"r = {squeeze_r}")
    print(f"theta = {theta}")
    print(f"bits = {bits}")
    print(f"m = {message_value}")
    print(f"beta_m = m(1 + i) = {fmt(message_beta)}")

    print_header("2. Prepare S(s)D(alpha)|0>")
    prepared_beta = squeeze_displace_forward(alpha, squeeze_r, theta)
    print("Formula:")
    print("beta = alpha cosh(r) + exp(i theta) alpha* sinh(r)")
    print("With r = 0: cosh(0) = 1 and sinh(0) = 0")
    print(f"beta = {fmt(alpha)} * 1 + exp(0i) * {fmt(alpha.conjugate())} * 0")
    print(f"beta = {fmt(prepared_beta)}")
    print(f"Prepared state: S(0)D(alpha)|0> = D({fmt(prepared_beta)})|0>")

    print_header("3. Control check example")
    control_after_unsqueeze = squeeze_displace_inverse(prepared_beta, squeeze_r, theta)
    print("Formula:")
    print("alpha_recovered = beta cosh(r) - exp(i theta) beta* sinh(r)")
    print(f"alpha_recovered = {fmt(control_after_unsqueeze)}")
    print(f"q measurement should be Re(alpha) = {control_after_unsqueeze.real:g}")
    print(f"p measurement should be Im(alpha) = {control_after_unsqueeze.imag:g}")

    print_header("4. Encode the message")
    print("Formula:")
    print("beta_m = m + i m")
    print(f"beta_m = {message_value:g} + i{message_value:g} = {fmt(message_beta)}")
    print(f"{message_value:g} lies in interval (2, 3), so bits = {bits}")

    print_header("5. Receive and unsqueeze")
    delta = displacement_after_unsqueeze(message_beta, squeeze_r, theta)
    returned_alpha = alpha + delta
    print("Formula:")
    print("Delta = beta_m cosh(r) - exp(i theta) beta_m* sinh(r)")
    print(f"Delta = {fmt(message_beta)} * 1 - exp(0i) * {fmt(message_beta.conjugate())} * 0")
    print(f"Delta = {fmt(delta)}")
    print(f"alpha_measured = alpha + Delta = {fmt(alpha)} + {fmt(delta)}")
    print(f"alpha_measured = {fmt(returned_alpha)}")

    print_header("6. Decode")
    observed_delta = returned_alpha - alpha
    recovered_beta = recover_message_displacement(observed_delta, squeeze_r, theta)
    decoded_value = (recovered_beta.real + recovered_beta.imag) / 2.0
    decoded_bits = bits_for_real(decoded_value)
    print("Formula:")
    print("observed_delta = alpha_measured - alpha")
    print(f"observed_delta = {fmt(returned_alpha)} - {fmt(alpha)} = {fmt(observed_delta)}")
    print("beta_m_recovered = observed_delta cosh(r) + exp(i theta) observed_delta* sinh(r)")
    print(f"beta_m_recovered = {fmt(recovered_beta)}")
    print("m_recovered = (Re(beta_m_recovered) + Im(beta_m_recovered)) / 2")
    print(
        "m_recovered = "
        f"({recovered_beta.real:g} + {recovered_beta.imag:g}) / 2 = {decoded_value:g}"
    )
    print(f"decoded bits = {decoded_bits}")


def print_header(title: str) -> None:
    print()
    print("=" * len(title))
    print(title)
    print("=" * len(title))


def fmt(value: complex) -> str:
    sign = "+" if value.imag >= 0 else "-"
    return f"{value.real:g} {sign} {abs(value.imag):g}i"


if __name__ == "__main__":
    main()
