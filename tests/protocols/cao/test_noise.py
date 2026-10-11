from math import sqrt
from statistics import fmean, pvariance

import numpy as np
import pytest
import strawberryfields as sf
from strawberryfields import ops

from qsdc.common.random import ClassicalRandomSource, weighted_random_bits
from qsdc.protocols.cao.config import NOISES, SimulatorConfig
from qsdc.protocols.cao.simulator.backends import AnalyticBackend
from qsdc.protocols.cao.simulator.protocol import Simulator

SQUEEZE_R = 1.0
NOISE = NOISES["metro_10km"]
# Alice displaces after her delay line, so only the fibre and the detector attenuate it.
GAIN = sqrt(NOISE.bob_detector.efficiency * NOISE.channel.transmittance / 2)


def epr_covariance(signal_links, detection_links):
    program = sf.Program(2)
    with program.context as q:
        ops.Sgate(SQUEEZE_R, 0.0) | q[0]
        ops.Sgate(SQUEEZE_R, np.pi) | q[1]
        ops.BSgate(np.pi / 4, 0.0) | (q[0], q[1])
        for link in signal_links:
            ops.ThermalLossChannel(link.transmittance, link.nbar) | q[1]
        for link in detection_links:
            ops.ThermalLossChannel(link.transmittance, link.nbar) | q[0]
    return sf.Engine("gaussian").run(program).state.cov()


def difference_variance(covariance):
    # S1 is mode 1 and S2 is mode 0 rotated by pi, so x_S1 - x_S2 = x1 + x0.
    weights = np.array([1.0, 1.0, 0.0, 0.0])
    return weights @ covariance @ weights


def detected(variance, detector):
    eta = detector.efficiency
    return eta * variance + (1 - eta) + detector.electronic_variance


def draws(backend, method, *args, count=40_000):
    backend.begin_run(3)
    return [getattr(backend, method)(*args) for _ in range(count)]


def test_joint_measurement_matches_strawberry_fields():
    covariance = epr_covariance(
        [NOISE.alice_memory, NOISE.channel], [NOISE.channel, NOISE.bob_memory]
    )
    expected = detected(difference_variance(covariance) / 2, NOISE.bob_detector)

    measured = draws(AnalyticBackend(SQUEEZE_R, NOISE), "measure_signal", 2 + 0j)

    assert fmean(m.real for m in measured) == pytest.approx(2 * GAIN, abs=0.01)
    assert pvariance([m.real for m in measured]) == pytest.approx(expected, rel=0.03)
    assert pvariance([m.imag for m in measured]) == pytest.approx(expected, rel=0.03)


def test_checks_match_strawberry_fields():
    covariance = epr_covariance([NOISE.alice_memory], [NOISE.channel])
    heterodyne = (difference_variance(covariance) + 2) / 2
    detector = NOISE.alice_detector
    # Each party's detector adds its own loss and electronic noise.
    expected = (detected(heterodyne, detector) + detected(0.0, detector)) / 2

    checks = draws(AnalyticBackend(SQUEEZE_R, NOISE), "measure_check")
    x = [(alice.real - bob.real) / sqrt(2) for alice, bob in checks]

    assert pvariance(x) == pytest.approx(expected, rel=0.03)


def test_the_gain_estimate_follows_the_loss():
    config = SimulatorConfig(noise=NOISE, check_failure_threshold=1.01)
    payload = weighted_random_bits(200, 0.5, ClassicalRandomSource(4))

    transmission = Simulator(config).transmit(payload)

    gains = [a.run.estimate.gain for a in transmission.attempts if a.run.estimate]
    assert fmean(gains) == pytest.approx(GAIN, rel=0.03)


@pytest.mark.parametrize("name", ["lab", "metro_10km"])
def test_noise_raises_the_check_failures(name):
    clean = draws(AnalyticBackend(SQUEEZE_R), "measure_check", count=20_000)
    noisy = draws(
        AnalyticBackend(SQUEEZE_R, NOISES[name]), "measure_check", count=20_000
    )

    def failure_rate(checks):
        return fmean(
            ((a.real - b.real) ** 2 + (a.imag + b.imag) ** 2) / 2 >= 2
            for a, b in checks
        )

    assert failure_rate(noisy) > failure_rate(clean)


def test_clean_baseline_is_the_default():
    assert NOISES["clean"] == SimulatorConfig().noise
