from math import cosh, exp, pi, sinh, sqrt

import pytest

from qsdc.protocols.srikara.benchmark.catalog import NOISES
from qsdc.protocols.srikara.config import SimulatorConfig
from qsdc.protocols.srikara.simulator.backends import AnalyticBackend, PreparedState
from qsdc.protocols.srikara.simulator.protocol import AXES, SrikaraSimulator

PAYLOAD = "101001110010011010001101110"


@pytest.mark.parametrize("backend", ["analytic", "sf"])
@pytest.mark.parametrize("error_correction", ["none", "parity", "secded"])
def test_ideal_backends_deliver_the_payload(backend, error_correction):
    config = SimulatorConfig(backend=backend, error_correction=error_correction)
    transmission = SrikaraSimulator(config).transmit(PAYLOAD)

    assert transmission.recovered_bits == PAYLOAD
    for attempt in transmission.attempts:
        n = len(attempt.run.states)
        route = attempt.run.route
        assert (len(route.control), len(route.message), len(route.decoy)) == (
            n // 2,
            n // 4,
            n // 4,
        )


def test_transmission_is_reproducible_from_the_seed():
    config = SimulatorConfig(
        backend="sf-sampled", noise=NOISES["medium"], tolerance_sigmas=3.0
    )
    first = SrikaraSimulator(config).transmit(PAYLOAD)

    assert SrikaraSimulator(config).transmit(PAYLOAD) == first
    assert (
        SrikaraSimulator(config.model_copy(update={"seed": 12})).transmit(PAYLOAD)
        != first
    )


def test_best_qp_axis_policy_reads_the_quadrature_with_the_larger_response():
    backend = AnalyticBackend()
    transmission = SrikaraSimulator(
        SimulatorConfig(axis_policy="best_qp"), backend
    ).transmit(PAYLOAD)

    for attempt in transmission.attempts:
        for message in attempt.run.messages:
            state = attempt.run.states[message.index]
            assert abs(message.response) == max(
                abs(backend.message_response(state, axis)) for axis in AXES
            )


def test_decoy_checks_reject_a_disturbed_channel(eavesdropper):
    transmission = SrikaraSimulator(SimulatorConfig(), eavesdropper()).transmit(PAYLOAD)

    for attempt in transmission.attempts:
        assert all(check.passed for check in attempt.run.controls)
        assert not any(check.passed for check in attempt.run.decoys)
    assert transmission.recovered_bits is None


def test_secded_corrects_one_wrong_symbol_per_block(corrupt_first_message):
    uncoded = SrikaraSimulator(SimulatorConfig(), corrupt_first_message()).transmit(
        PAYLOAD
    )
    coded = SrikaraSimulator(
        SimulatorConfig(error_correction="secded"), corrupt_first_message()
    ).transmit(PAYLOAD)

    assert uncoded.recovered_bits != PAYLOAD
    assert coded.recovered_bits == PAYLOAD


def test_rejected_blocks_are_retried_until_recovered(reject_every_other_run):
    single = SrikaraSimulator(SimulatorConfig(), reject_every_other_run()).transmit(
        PAYLOAD
    )
    retried = SrikaraSimulator(
        SimulatorConfig(max_attempts=2), reject_every_other_run()
    ).transmit(PAYLOAD)

    assert single.recovered_bits is None
    assert retried.recovered_bits == PAYLOAD
    assert [attempt.number for attempt in retried.attempts] == [0, 1] * (
        len(PAYLOAD) // 3
    )


def test_aligned_axis_reads_the_full_message_displacement():
    backend = AnalyticBackend()
    config = SimulatorConfig(axis_policy="aligned")
    transmission = SrikaraSimulator(config, backend).transmit(PAYLOAD)

    assert transmission.recovered_bits == PAYLOAD
    for attempt in transmission.attempts:
        for message in attempt.run.messages:
            state = attempt.run.states[message.index]
            unit = AnalyticBackend.unsqueezed_displacement(
                1 + 1j, state.squeeze_r, state.theta
            )
            assert message.response == pytest.approx(abs(unit))
            assert message.response >= max(abs(unit.real), abs(unit.imag))


def test_theta_five_quarter_pi_gives_the_largest_message_response():
    backend, r = AnalyticBackend(), 0.576
    best = {}
    for theta_pi in (0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75):
        state = PreparedState(0, 0j, r, theta_pi * pi)
        best[theta_pi] = max(
            abs(backend.message_response(state, axis)) for axis in AXES
        )

    assert max(best, key=best.get) in (1.25, 1.75)
    assert best[1.25] == pytest.approx(cosh(r) + sqrt(2) * sinh(r))
    assert best[0.5] == pytest.approx(exp(-r))
