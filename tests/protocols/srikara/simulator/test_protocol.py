import pytest

from qsdc.protocols.srikara.simulator.backends.analytic.ideal import AnalyticBackend
from qsdc.protocols.srikara.simulator.backends.base import MeasurementExpectation
from qsdc.protocols.srikara.configuration.configs import ProtocolConfig
from qsdc.protocols.srikara.simulator.protocol import simulate_qsdc


def test_qsdc_protocol_round_trips_messages():
    messages = ("000", "011", "101")
    result = simulate_qsdc(
        messages,
        config=ProtocolConfig.from_options(n_states=12, seed=4),
        backend=AnalyticBackend(),
    )

    assert result.accepted
    assert [message.decoded_bits for message in result.messages] == list(messages)
    assert len(result.control_indices) == 6
    assert len(result.decoy_indices) == 3
    assert len(result.message_indices) == 3
    assert len(result.route.delayed_indices) == 6
    assert result.transcript.random_source == "classical"


def test_check_axis_policy_uses_larger_displacement_component():
    messages = ("000", "011", "101")
    result = simulate_qsdc(
        messages,
        config=ProtocolConfig.from_options(
            n_states=12,
            seed=4,
            check_axis_policy="optimized",
        ),
        backend=AnalyticBackend(),
    )
    state_by_index = {state.index: state for state in result.prepared_states}

    for check in (*result.controls, *result.decoys):
        state = state_by_index[check.index]
        expected_axis = "q" if abs(state.alpha.real) >= abs(state.alpha.imag) else "p"
        assert check.axis == expected_axis


def test_protocol_uses_calibrated_expectations_for_checks_and_messages():
    class CalibratedBackend(AnalyticBackend):
        def control_expectation(self, alpha, squeeze_r, theta, axis):
            return MeasurementExpectation(mean=10.0, sigma=2.0)

        def returned_expectation(self, alpha, squeeze_r, theta, axis):
            return MeasurementExpectation(mean=-4.0, sigma=3.0)

        def control_measurement(self, alpha, squeeze_r, theta, axis):
            return 10.0

        def returned_measurement(
            self,
            alpha,
            squeeze_r,
            theta,
            beta,
            axis,
        ):
            return -4.0 + self.message_response_factor(
                squeeze_r,
                theta,
                axis,
            ) * beta.real

    messages = ("000", "011", "101")
    result = simulate_qsdc(
        messages,
        config=ProtocolConfig.from_options(n_states=12, seed=4),
        backend=CalibratedBackend(),
    )

    assert result.accepted
    assert all(check.expected == 10.0 for check in result.controls)
    assert all(check.expected_sigma == 2.0 for check in result.controls)
    assert all(check.expected == -4.0 for check in result.decoys)
    assert all(check.expected_sigma == 3.0 for check in result.decoys)
    assert all(message.expected_baseline == -4.0 for message in result.messages)
    assert [message.decoded_bits for message in result.messages] == list(messages)
