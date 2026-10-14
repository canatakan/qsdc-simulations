from math import sqrt
from statistics import fmean, pvariance

import pytest

from qsdc.common.random import ClassicalRandomSource, weighted_random_bits
from qsdc.protocols.cao.config import NOISES, SimulatorConfig
from qsdc.protocols.cao.simulator.backends import (
    AnalyticBackend,
    SFAnalyticBackend,
    SFSampledBackend,
)
from qsdc.protocols.cao.simulator.protocol import Simulator

SQUEEZE_R = 1.0
SAMPLES = 2000


def draws(backend, method, *args):
    backend.prepare_run(3)
    return [getattr(backend, method)(*args) for _ in range(SAMPLES)]


def check_differences(checks):
    x = [(alice.real - bob.real) / sqrt(2) for alice, bob in checks]
    p = [(alice.imag + bob.imag) / sqrt(2) for alice, bob in checks]
    return x, p


@pytest.mark.parametrize("squeeze_r", [0.5, 1.4436])
def test_analytic_check_sigma_equals_strawberry_fields(squeeze_r):
    analytic = AnalyticBackend(squeeze_r).check_sigma()
    circuit = SFSampledBackend(squeeze_r).check_sigma()

    assert analytic == pytest.approx(circuit)


@pytest.mark.parametrize("name", ["clean", "metro_10km"])
def test_sampled_checks_have_the_expected_variance(name):
    backend = SFSampledBackend(SQUEEZE_R, NOISES[name])

    x, p = check_differences(draws(backend, "measure_check"))

    assert fmean(x) == pytest.approx(0.0, abs=0.06)
    assert pvariance(x) == pytest.approx(backend.check_sigma() ** 2, rel=0.1)
    assert pvariance(p) == pytest.approx(backend.check_sigma() ** 2, rel=0.1)


@pytest.mark.parametrize("name", ["clean", "metro_10km"])
def test_sampled_joint_measurement_has_the_exact_mean(name):
    noise = NOISES[name]
    displacement = 2 - 1j
    expected = SFAnalyticBackend(SQUEEZE_R, noise).measure_signal(displacement)

    measured = draws(SFSampledBackend(SQUEEZE_R, noise), "measure_signal", displacement)

    assert fmean(m.real for m in measured) == pytest.approx(expected.real, abs=0.05)
    assert fmean(m.imag for m in measured) == pytest.approx(expected.imag, abs=0.05)


def test_the_gain_estimate_follows_the_loss():
    noise = NOISES["metro_10km"]
    config = SimulatorConfig(noise=noise)
    payload = weighted_random_bits(200, 0.5, ClassicalRandomSource(4))

    transmission = Simulator(config).transmit(payload)

    gains = [run.estimate.gain for run in transmission.runs if run.estimate]
    expected = SFAnalyticBackend(config.squeeze_r, noise).measure_signal(1).real
    assert fmean(gains) == pytest.approx(expected, rel=0.03)


def test_noise_raises_the_check_failures():
    def failure_rate(name):
        backend = SFSampledBackend(SQUEEZE_R, NOISES[name])
        x, p = check_differences(draws(backend, "measure_check"))
        return fmean(xi * xi + pi * pi >= 2 for xi, pi in zip(x, p))

    assert failure_rate("clean") < failure_rate("metro_10km")


def test_clean_baseline_and_strawberry_fields_are_the_defaults():
    config = SimulatorConfig()

    assert config.noise == NOISES["clean"]
    assert config.backend == "sf-sampled"


def test_calibrated_checks_accept_honest_blocks_at_27km():
    payload = weighted_random_bits(1024, 0.5, ClassicalRandomSource(8))
    config = SimulatorConfig(noise=NOISES["record_27km"])

    transmission = Simulator(config).transmit(payload)

    assert all(attempt.accepted for attempt in transmission.attempts)
