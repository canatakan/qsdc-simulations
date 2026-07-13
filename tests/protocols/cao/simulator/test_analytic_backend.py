from math import isclose

from qsdc.protocols.cao.simulator.backends.analytic.ideal import AnalyticBackend
from qsdc.protocols.cao.simulator.backends.base import VacuumQuadratures


def test_analytic_backend_recovers_modulation_plus_correlation_noise():
    backend = AnalyticBackend()
    beams = backend.prepare_correlated_beams(
        squeeze_r=0.7,
        vacuum=VacuumQuadratures(x1=0.2, p1=-0.4, x2=0.5, p2=0.1),
    )
    noise = backend.correlation_noise(beams)
    modulated = backend.modulate(beams, x_value=1.25, p_value=-0.75)
    measured = backend.measure_message(modulated)

    assert isclose(measured.x_message, 1.25 + noise.delta_x)
    assert isclose(measured.p_message, -0.75 + noise.delta_p)


def test_analytic_backend_has_zero_noise_for_zero_vacuum_input():
    backend = AnalyticBackend()
    beams = backend.prepare_correlated_beams(
        squeeze_r=0.7,
        vacuum=VacuumQuadratures(x1=0.0, p1=0.0, x2=0.0, p2=0.0),
    )
    noise = backend.correlation_noise(beams)

    assert noise.delta_x == 0.0
    assert noise.delta_p == 0.0
