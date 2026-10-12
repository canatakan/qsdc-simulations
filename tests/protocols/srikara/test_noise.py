import numpy as np
import pytest

from qsdc.common.config.noise import Channel, Detector, Memory
from qsdc.common.quadrature import Q
from qsdc.protocols.srikara.benchmark.catalog import NOISES
from qsdc.protocols.srikara.config import NoiseConfig, SimulatorConfig
from qsdc.protocols.srikara.simulator.backends import (
    PreparedState,
    SFSampledBackend,
)
from qsdc.protocols.srikara.simulator.protocol import Simulator

COHERENT = PreparedState(index=0, alpha=1.5 + 0j, squeeze_r=0.0, theta=0.0)


def test_returned_expectation_follows_the_gaussian_channel_formulas():
    noise = NoiseConfig(
        backward=Channel(transmittance=0.64, nbar=0.5),
        bob_detector=Detector(efficiency=0.64, electronic_variance=0.5),
    )
    expectation = SFSampledBackend(noise).expect_returned(COHERENT, Q)

    vacuum = 0.25
    after_channel = 0.64 * vacuum + 0.36 * (2 * 0.5 + 1) * vacuum
    after_detector = 0.64 * after_channel + 0.36 * vacuum
    assert expectation.mean == pytest.approx(0.8 * 0.8 * 1.5)
    assert expectation.sigma == pytest.approx(np.sqrt(after_detector + 0.5 * vacuum))


def test_memory_loss_attenuates_bobs_state_but_not_alices_message():
    noise = NoiseConfig(memory=Memory(seconds=np.log(1 / 0.64), lifetime_seconds=1.0))
    backend = SFSampledBackend(noise)

    assert backend.expect_returned(COHERENT, Q).mean == pytest.approx(0.8 * 1.5)
    assert backend.message_response(COHERENT, Q) == pytest.approx(1.0)


def test_sampled_measurements_scatter_around_the_expectation():
    noise = NoiseConfig(
        forward=Channel(transmittance=0.9, nbar=0.1),
        alice_detector=Detector(efficiency=0.8, electronic_variance=0.5),
    )
    backend = SFSampledBackend(noise)
    state = PreparedState(index=0, alpha=1 - 0.5j, squeeze_r=0.6, theta=0.3)
    backend.begin_run(5)

    samples = [backend.measure_control(state, Q) for _ in range(400)]
    expectation = backend.expect_control(state, Q)
    assert np.mean(samples) == pytest.approx(
        expectation.mean, abs=4 * expectation.sigma / 20
    )
    assert np.std(samples) == pytest.approx(expectation.sigma, rel=0.15)


def test_calibrated_checks_accept_an_honest_noisy_channel():
    config = SimulatorConfig(
        backend="sf-sampled", noise=NOISES["metro_10km"], tolerance_sigmas=4.0
    )
    transmission = Simulator(config).transmit("101001110010" * 3)

    assert all(attempt.run.accepted for attempt in transmission.attempts)
