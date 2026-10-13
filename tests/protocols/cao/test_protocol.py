from math import exp, sqrt
from statistics import fmean, pvariance

import numpy as np
import pytest

from qsdc.common.coding.bits import bytes_to_bits
from qsdc.common.random import ClassicalRandomSource, weighted_random_bits
from qsdc.protocols.cao.config import NOISES, Reconciliation, SimulatorConfig
from qsdc.protocols.cao.constants import EPR_BOUND
from qsdc.protocols.cao.simulator.backends import (
    AnalyticBackend,
    SFSampledBackend,
)
from qsdc.protocols.cao.simulator.protocol import Simulator

SAMPLES = 2000


class InterceptedBackend(SFSampledBackend):
    # Eve keeps S2 and sends Bob a vacuum instead, whose heterodyne outcomes
    # have the variance of one vacuum.
    def measure_check(self):
        alice, _ = super().measure_check()
        return alice, complex(*np.random.normal(0.0, 1.0, 2))


class InvertFirstSignal(AnalyticBackend):
    def begin_run(self, seed):
        self.runs = getattr(self, "runs", 0) + 1
        self.inverted = self.runs > 1

    def measure_signal(self, displacement):
        value = super().measure_signal(displacement)
        if not self.inverted:
            self.inverted = True
            return -value
        return value


def samples(backend, method, *args):
    backend.begin_run(1)
    return [getattr(backend, method)(*args) for _ in range(SAMPLES)]


@pytest.mark.parametrize("squeeze_r", [0.0, 0.5, 1.4436])
def test_checks_follow_the_epr_correlations(squeeze_r):
    pairs = samples(SFSampledBackend(squeeze_r), "measure_check")
    x = [(a.real - b.real) / sqrt(2) for a, b in pairs]
    p = [(a.imag + b.imag) / sqrt(2) for a, b in pairs]
    variance = (1 + exp(-2 * squeeze_r)) / 2
    failures = [xi * xi + pi * pi >= EPR_BOUND for xi, pi in zip(x, p)]

    assert pvariance(x) == pytest.approx(variance, rel=0.1)
    assert pvariance(p) == pytest.approx(variance, rel=0.1)
    assert fmean(failures) == pytest.approx(exp(-1 / variance), abs=0.04)


def test_joint_measurement_reads_alice_s_displacement():
    squeeze_r = 1.0
    measured = samples(SFSampledBackend(squeeze_r), "measure_signal", 2 - 1j)

    assert fmean(m.real for m in measured) == pytest.approx(2 / sqrt(2), abs=0.03)
    assert fmean(m.imag for m in measured) == pytest.approx(-1 / sqrt(2), abs=0.03)
    assert pvariance([m.real for m in measured]) == pytest.approx(
        exp(-2 * squeeze_r), rel=0.08
    )


def test_analytic_backend_measures_without_noise():
    backend = AnalyticBackend(1.0)

    assert backend.measure_check() == (0j, 0j)
    assert backend.measure_signal(2 - 1j) == pytest.approx((2 - 1j) / sqrt(2))


def test_noiseless_round_trip():
    payload = bytes_to_bits(b"Gaussian mapping")
    simulator = Simulator(SimulatorConfig(backend="analytic"))

    transmission = simulator.transmit(payload)

    assert transmission.recovered_bits == payload
    assert all(
        attempt.run.estimate.gain == pytest.approx(1 / sqrt(2))
        for attempt in transmission.attempts
    )


def test_without_reconciliation_a_detected_error_is_retried():
    payload = "10"
    config = SimulatorConfig(
        boxes=4, check_pairs=4, reconciliation=None, max_attempts=2
    )

    transmission = Simulator(config, InvertFirstSignal(0.0)).transmit(payload)

    first, second = transmission.attempts
    assert first.run.accepted and first.decoded_bits is None
    assert not first.run.signals[0].parity_valid
    assert second.decoded_bits == payload


def test_reconciliation_corrects_a_wrong_box():
    config = SimulatorConfig()
    payload = weighted_random_bits(config.block_bits, 0.5, ClassicalRandomSource(6))

    transmission = Simulator(config, InvertFirstSignal(0.0)).transmit(payload)

    (attempt,) = transmission.attempts
    assert attempt.run.signals[0].decoded_bits != attempt.run.signals[0].box.bits
    assert attempt.decoded_bits == payload


@pytest.mark.parametrize("name", ["clean", "lab"])
def test_reconciliation_delivers_the_message(name):
    payload = weighted_random_bits(1024, 0.5, ClassicalRandomSource(7))
    config = SimulatorConfig(noise=NOISES[name], max_attempts=3)

    transmission = Simulator(config).transmit(payload)

    wrong = sum(
        s.decoded_bits != s.box.bits
        for a in transmission.attempts
        for s in a.run.signals
    )
    assert wrong > 0
    assert transmission.recovered_bits == payload


def test_without_reconciliation_the_raw_errors_withhold_blocks():
    payload = weighted_random_bits(1024, 0.5, ClassicalRandomSource(7))
    config = SimulatorConfig(noise=NOISES["lab"], reconciliation=None)

    transmission = Simulator(config).transmit(payload)

    assert transmission.recovered_bits is None


def test_intercepting_the_detection_light_is_detected():
    payload = weighted_random_bits(200, 0.5, ClassicalRandomSource(1))
    config = SimulatorConfig(check_pairs=16, max_attempts=3)

    transmission = Simulator(config, InterceptedBackend(config.squeeze_r)).transmit(
        payload
    )

    assert not any(attempt.run.accepted for attempt in transmission.attempts)
    assert all(not attempt.run.signals for attempt in transmission.attempts)
    assert transmission.recovered_bits is None


def test_honest_channel_passes_the_checks():
    payload = weighted_random_bits(1024, 0.5, ClassicalRandomSource(1))

    transmission = Simulator(SimulatorConfig()).transmit(payload)

    assert all(attempt.run.accepted for attempt in transmission.attempts)


def test_each_block_uses_its_pairs_once():
    config = SimulatorConfig()
    run = Simulator(config, AnalyticBackend(0.0)).transmit("10").attempts[0].run
    indices = [check.index for check in run.channel.checks + run.authentication.checks]
    indices += [signal.index for signal in run.signals]

    assert run.pairs == 2 * config.check_pairs + config.boxes
    assert sorted(indices) == list(range(run.pairs))


def test_transmission_is_reproducible():
    payload = weighted_random_bits(60, 0.5, ClassicalRandomSource(2))
    config = SimulatorConfig(max_attempts=3)

    first = Simulator(config).transmit(payload)
    second = Simulator(config).transmit(payload)

    assert first == second


def test_rejects_settings_without_secure_message_bits():
    with pytest.raises(ValueError):
        SimulatorConfig(reconciliation=Reconciliation(syndrome_fraction=0.5))
