import pytest

from qsdc.protocols.srikara.simulator.backends.analytic.ideal import AnalyticBackend
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
