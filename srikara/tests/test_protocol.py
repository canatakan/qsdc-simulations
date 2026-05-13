from simulator.backends import AnalyticBackend
from simulator.core.config import ProtocolConfig
from simulator.core.protocol import simulate_qsdc


def test_qsdc_protocol_round_trips_messages():
    messages = ("000", "011", "101")
    result = simulate_qsdc(
        messages,
        config=ProtocolConfig(n_states=12, seed=4),
        backend=AnalyticBackend(),
    )

    assert result.accepted
    assert [message.decoded_bits for message in result.messages] == list(messages)
    assert len(result.control_indices) == 6
    assert len(result.decoy_indices) == 3
    assert len(result.message_indices) == 3
