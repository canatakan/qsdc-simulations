from __future__ import annotations

from math import cosh, exp, pi, sinh, sqrt

from qsdc.protocols.srikara.simulator.backends import AnalyticBackend
from qsdc.protocols.srikara.simulator.encoding import INTERVAL_CODES, MESSAGE_DIRECTION
from qsdc.protocols.srikara.simulator.routing import ModeRoute

ROUTE = ModeRoute(control=(0, 1), delayed=(2, 3), message=(2,), decoy=(3,))
ALPHA = 2.0 + 3.0j
SQUEEZE_R = 0.0
THETA = 0.0
BITS = "110"
MESSAGE_VALUE = 2.5


def main() -> None:
    beta_a = MESSAGE_VALUE * MESSAGE_DIRECTION

    header("1. Fixed inputs")
    print(
        f"n = 4 modes: control {ROUTE.control}, message {ROUTE.message}, decoy {ROUTE.decoy}"
    )
    print(f"alpha = {fmt(ALPHA)}, r = {SQUEEZE_R}, theta = {THETA}")
    print(f"bits = {BITS}, m_A = {MESSAGE_VALUE}, beta_A = m_A(1 + i) = {fmt(beta_a)}")

    header("2. Bob prepares S(s)D(alpha)|0> = D(beta)S(s)|0>")
    prepared = AnalyticBackend.squeezed_displacement(ALPHA, SQUEEZE_R, THETA)
    print("beta = alpha cosh(r) + exp(i theta) alpha* sinh(r)")
    print(
        f"     = ({fmt(ALPHA)}) * 1 + ({fmt(ALPHA.conjugate())}) * 0 = {fmt(prepared)}"
    )
    print("Alice -> Bob: coordinates of the control modes")

    header("3. Alice checks a control mode")
    print("Bob -> Alice: s and alpha of the control modes")
    control = AnalyticBackend.unsqueezed_displacement(prepared, SQUEEZE_R, THETA)
    print("After S(-s): beta cosh(r) - exp(i theta) beta* sinh(r)")
    print(f"           = {fmt(control)}")
    print(
        f"q should read Re(alpha) = {control.real:g}, p should read Im(alpha) = {control.imag:g}"
    )

    header("4. Alice encodes the message mode")
    print(f"{MESSAGE_VALUE:g} lies in (2, 3), the interval of {BITS}: D({fmt(beta_a)})")
    print("Alice -> Bob: coordinates of the decoy modes")

    header("5. Bob unsqueezes the returned mode")
    delta = AnalyticBackend.unsqueezed_displacement(beta_a, SQUEEZE_R, THETA)
    print("Delta = beta_A cosh(r) - exp(i theta) beta_A* sinh(r)")
    print(f"      = {fmt(delta)}")
    print(f"measured displacement = alpha + Delta = {fmt(ALPHA + delta)}")

    header("6. Bob decodes")
    recovered = AnalyticBackend.squeezed_displacement(delta, SQUEEZE_R, THETA)
    decoded_value = (recovered.real + recovered.imag) / 2.0
    print(f"beta_A = Delta cosh(r) + exp(i theta) Delta* sinh(r) = {fmt(recovered)}")
    print(f"m_A = (Re + Im) / 2 = {decoded_value:g}")
    print(f"decoded bits = {INTERVAL_CODES['default'].decode(decoded_value)}")

    squeezed_example(beta_a)


def squeezed_example(beta_a: complex) -> None:
    header("7. The same symbol with squeezing, r = 0.5")
    r = 0.5
    print("Bob measures one quadrature of alpha + Delta and divides by the response")
    print("Delta(m_A = 1) on that quadrature. With beta_A along 1 + i, the angle theta")
    print("decides whether S(-s) stretches or shrinks Alice's displacement:")
    rows = []
    for theta_pi in (0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75):
        theta = theta_pi * pi
        unit = AnalyticBackend.unsqueezed_displacement(MESSAGE_DIRECTION, r, theta)
        delta = AnalyticBackend.unsqueezed_displacement(beta_a, r, theta)
        axis = "q" if abs(unit.real) >= abs(unit.imag) else "p"
        response = unit.real if axis == "q" else unit.imag
        shift = delta.real if axis == "q" else delta.imag
        rows.append((theta_pi, fmt(unit), axis, response, shift, shift / response))
    print(
        f"\n{'theta/pi':>8}  {'Delta(m=1)':>18}  axis  {'response':>8}  {'shift':>8}  m_A"
    )
    for theta_pi, unit, axis, response, shift, value in rows:
        print(
            f"{theta_pi:>8g}  {unit:>18}  {axis:>4}  {response:>8.4f}  {shift:>8.4f}  {value:g}"
        )
    print(
        f"\ncosh r + sqrt(2) sinh r = {cosh(r) + sqrt(2) * sinh(r):.4f} (best, theta = 5pi/4 or 7pi/4)"
    )
    print(f"exp(-r)                 = {exp(-r):.4f} (worst, theta = pi/2)")
    print("Without noise every angle decodes m_A exactly; with homodyne noise of fixed")
    print("size, a larger response means a smaller error in the decoded m_A.")


def header(title: str) -> None:
    print(f"\n{title}\n{'=' * len(title)}")


def fmt(value: complex) -> str:
    sign = "+" if value.imag >= 0 else "-"
    return f"{value.real:g} {sign} {abs(value.imag):g}i"


if __name__ == "__main__":
    main()
