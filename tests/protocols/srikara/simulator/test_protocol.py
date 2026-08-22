import pytest

from qsdc.protocols.srikara.configuration.simulator import SimulatorConfig
from qsdc.protocols.srikara.simulator.backends.analytic.ideal import AnalyticBackend
from qsdc.protocols.srikara.simulator.backends.base import MeasurementExpectation
from qsdc.protocols.srikara.simulator.encoding import bits_for_real, interval_for_bits
from qsdc.protocols.srikara.simulator.protocol import simulate_qsdc


class FirstMessageDropoutBackend(AnalyticBackend):
    def begin_run(self, seed):
        object.__setattr__(self, "_message_count", 0)

    def returned_measurement(self, alpha, squeeze_r, theta, beta, axis):
        if beta != 0j:
            object.__setattr__(self, "_message_count", self._message_count + 1)
            if self._message_count == 1:
                return None
        return super().returned_measurement(alpha, squeeze_r, theta, beta, axis)


class TwoMessageErrorsBackend(AnalyticBackend):
    def begin_run(self, seed):
        object.__setattr__(self, "_message_count", 0)

    def returned_measurement(self, alpha, squeeze_r, theta, beta, axis):
        if beta == 0j:
            return super().returned_measurement(alpha, squeeze_r, theta, beta, axis)
        object.__setattr__(self, "_message_count", self._message_count + 1)
        if self._message_count > 2:
            return super().returned_measurement(alpha, squeeze_r, theta, beta, axis)
        sent = bits_for_real(beta.real)
        forced = "".join("1" if bit == "0" else "0" for bit in sent)
        interval = interval_for_bits(forced)
        forced_value = (
            interval.upper - 1.0
            if interval.lower == float("-inf")
            else interval.lower + 1.0
            if interval.upper == float("inf")
            else (interval.lower + interval.upper) / 2.0
        )
        response = self.message_response_factor(squeeze_r, theta, axis)
        baseline = self.returned_expectation(alpha, squeeze_r, theta, axis).mean
        return baseline + response * forced_value


class InvalidControlBackend(AnalyticBackend):
    def control_measurement(self, alpha, squeeze_r, theta, axis):
        return None


class FailSelectedRunsBackend(AnalyticBackend):
    def __init__(self, failed_runs):
        object.__setattr__(self, "failed_runs", set(failed_runs))
        object.__setattr__(self, "run_index", -1)

    def begin_run(self, seed):
        object.__setattr__(self, "run_index", self.run_index + 1)

    def control_measurement(self, alpha, squeeze_r, theta, axis):
        if self.run_index in self.failed_runs:
            return None
        return super().control_measurement(alpha, squeeze_r, theta, axis)


def _secded_config(seed=4, attempts=1):
    return SimulatorConfig(
        seed=seed,
        error_correction="secded",
        max_attempts_per_block=attempts,
    )


def test_qsdc_protocol_round_trips_payload():
    result = simulate_qsdc("000011101", SimulatorConfig(seed=4))
    protocol = result.blocks[0].protocol

    assert result.recovered_bits == "000011101"
    assert protocol.accepted
    assert [message.decoded_bits for message in protocol.messages] == [
        "000",
        "011",
        "101",
    ]
    assert len(protocol.control_indices) == 6
    assert len(protocol.decoy_indices) == 3
    assert len(protocol.message_indices) == 3
    assert protocol.transcript.random_source == "classical"


def test_check_axis_policy_uses_larger_normalized_quadrature():
    result = simulate_qsdc(
        "000011101",
        SimulatorConfig(seed=4, check_axis_policy="optimized"),
    )
    protocol = result.blocks[0].protocol
    state_by_index = {state.index: state for state in protocol.prepared_states}

    for check in (*protocol.controls, *protocol.decoys):
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

        def returned_measurement(self, alpha, squeeze_r, theta, beta, axis):
            return (
                -4.0
                + self.message_response_factor(
                    squeeze_r,
                    theta,
                    axis,
                )
                * beta.real
            )

    result = simulate_qsdc(
        "000011101",
        SimulatorConfig(seed=4),
        backend=CalibratedBackend(),
    )
    protocol = result.blocks[0].protocol

    assert protocol.accepted
    assert all(check.expected == 10.0 for check in protocol.controls)
    assert all(check.expected_sigma == 2.0 for check in protocol.controls)
    assert all(check.expected == -4.0 for check in protocol.decoys)
    assert all(message.expected_baseline == -4.0 for message in protocol.messages)


@pytest.mark.parametrize("invalid", [None, float("nan"), float("inf"), float("-inf")])
def test_invalid_control_measurements_reject_the_payload(invalid):
    class InvalidBackend(AnalyticBackend):
        def control_measurement(self, alpha, squeeze_r, theta, axis):
            return invalid

    result = simulate_qsdc("000111", SimulatorConfig(seed=3), InvalidBackend())
    protocol = result.blocks[0].protocol

    assert result.delivery_status == "protocol_rejected"
    assert result.recovered_bits is None
    assert all(check.status == "invalid_measurement" for check in protocol.controls)


@pytest.mark.parametrize("invalid", [None, float("nan"), float("inf"), float("-inf")])
def test_invalid_decoy_measurements_reject_the_payload(invalid):
    class InvalidBackend(AnalyticBackend):
        def returned_measurement(self, alpha, squeeze_r, theta, beta, axis):
            if beta == 0j:
                return invalid
            return super().returned_measurement(alpha, squeeze_r, theta, beta, axis)

    result = simulate_qsdc("000111", SimulatorConfig(seed=3), InvalidBackend())
    protocol = result.blocks[0].protocol

    assert protocol.control_passed
    assert not protocol.decoy_passed
    assert result.delivery_status == "protocol_rejected"


@pytest.mark.parametrize("invalid", [None, float("nan"), float("inf"), float("-inf")])
def test_invalid_message_measurements_are_erasures(invalid):
    class InvalidBackend(AnalyticBackend):
        def returned_measurement(self, alpha, squeeze_r, theta, beta, axis):
            if beta != 0j:
                return invalid
            return super().returned_measurement(alpha, squeeze_r, theta, beta, axis)

    result = simulate_qsdc("000111", SimulatorConfig(seed=3), InvalidBackend())
    protocol = result.blocks[0].protocol

    assert protocol.accepted
    assert result.delivery_status == "uncorrectable"
    assert all(message.decoded_bits is None for message in protocol.messages)


def test_enabled_no_noise_round_trip_uses_independent_blocks():
    payload = "101001110010" * 2
    result = simulate_qsdc(payload, _secded_config())

    assert result.delivery_status == "recovered"
    assert result.recovered_bits == payload
    assert len(result.blocks) == 2
    assert all(len(block.protocol.prepared_states) == 32 for block in result.blocks)
    assert result.frame.coded_bit_count == 48
    assert result.frame.nominal_code_rate == 0.5


def test_one_message_dropout_becomes_three_recoverable_erasures():
    result = simulate_qsdc(
        "101001110010",
        _secded_config(),
        FirstMessageDropoutBackend(),
    )
    attempt = result.blocks[0]

    assert attempt.protocol.accepted
    assert attempt.decode.recovered_erasures == 3
    assert result.recovered_bits == "101001110010"


def test_two_bad_symbols_are_detected_and_not_delivered():
    result = simulate_qsdc(
        "101001110010",
        _secded_config(),
        TwoMessageErrorsBackend(),
    )

    assert result.accepted
    assert result.delivery_status == "uncorrectable"
    assert result.recovered_bits is None
    assert result.exhausted_blocks == (0,)


def test_protocol_rejection_gates_error_correction():
    result = simulate_qsdc(
        "101001110010",
        _secded_config(),
        InvalidControlBackend(),
    )
    attempt = result.blocks[0]

    assert not attempt.protocol.accepted
    assert attempt.decode is None
    assert result.recovered_bits is None


def test_selective_retry_keeps_successful_blocks_and_reassembles_in_order():
    payload = "101001110010" + "011010001101"
    backend = FailSelectedRunsBackend({1})
    result = simulate_qsdc(payload, _secded_config(seed=10, attempts=2), backend)

    assert result.delivery_status == "recovered"
    assert result.recovered_bits == payload
    assert [
        (attempt.block.index, attempt.attempt_index) for attempt in result.attempts
    ] == [
        (0, 0),
        (1, 0),
        (1, 1),
    ]
    assert result.total_state_count == 96


def test_retry_exhaustion_never_releases_partial_payload():
    result = simulate_qsdc(
        "101001110010" * 2,
        _secded_config(attempts=2),
        FailSelectedRunsBackend({1, 2}),
    )

    assert result.delivery_status == "retry_exhausted"
    assert result.exhausted_blocks == (1,)
    assert result.recovered_bits is None
    assert result.blocks[0].recovered_bits is not None
    assert result.blocks[1].recovered_bits is None


def test_retry_configuration_is_validated_before_simulation():
    with pytest.raises(ValueError):
        SimulatorConfig(max_attempts_per_block=2)
