"""The complete Srikara protocol, from logical payload to decoded payload."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from math import isfinite
from typing import Literal, Optional

from qsdc.common.quadrature import QuadratureAxis
from qsdc.common.random import make_random_source
from qsdc.common.random.base import RandomSource
from qsdc.protocols.srikara.configuration.simulator import (
    AxisPolicy,
    IntervalPolicy,
    SimulatorConfig,
)
from qsdc.protocols.srikara.simulator.backends import make_backend
from qsdc.protocols.srikara.simulator.backends.base import QSDCBackend
from qsdc.protocols.srikara.simulator.encoding import (
    beta_for_message_value,
    bits_for_real,
    sample_message_value,
)
from qsdc.protocols.srikara.simulator.flow import (
    ModeRoute,
    OpticalSwitch,
    ProtocolTranscript,
    build_transcript,
)
from qsdc.protocols.srikara.simulator.transport import (
    TransportBlock,
    TransportDecode,
    TransportFrame,
    decode_block,
    encode_payload,
)

CheckStatus = Literal["passed", "out_of_tolerance", "invalid_measurement"]
AttemptStatus = Literal["recovered", "protocol_rejected", "uncorrectable"]
DeliveryStatus = Literal[
    "recovered",
    "protocol_rejected",
    "uncorrectable",
    "retry_exhausted",
]


@dataclass(frozen=True)
class BobPreparedState:
    index: int
    alpha: complex
    squeeze_r: float
    theta: float


@dataclass(frozen=True)
class ChannelCheck:
    index: int
    axis: QuadratureAxis
    expected: float
    expected_sigma: float
    measured: Optional[float]
    status: CheckStatus

    @property
    def passed(self) -> bool:
        return self.status == "passed"


@dataclass(frozen=True)
class MessageDecode:
    index: int
    intervals: IntervalPolicy
    sent_bits: str
    message_value: float
    alice_beta: complex
    axis: QuadratureAxis
    measured: Optional[float]
    expected_baseline: Optional[float]
    observed_delta: Optional[float]
    response_factor: Optional[float]
    decoded_value: Optional[float]
    decoded_bits: Optional[str]
    status: Literal["decoded", "invalid_measurement"] = "decoded"


@dataclass(frozen=True)
class ProtocolBlockResult:
    """Physical protocol observations for one transport-block attempt."""

    backend_name: str
    random_source_name: str
    check_tolerance_sigmas: float
    intervals: IntervalPolicy
    check_axis_policy: AxisPolicy
    message_axis_policy: AxisPolicy
    measurement_noise_sigma: float
    route: ModeRoute
    transcript: ProtocolTranscript
    prepared_states: tuple[BobPreparedState, ...]
    controls: tuple[ChannelCheck, ...]
    decoys: tuple[ChannelCheck, ...]
    messages: tuple[MessageDecode, ...]

    @property
    def control_passed(self) -> bool:
        return all(check.passed for check in self.controls)

    @property
    def decoy_passed(self) -> bool:
        return all(check.passed for check in self.decoys)

    @property
    def accepted(self) -> bool:
        return self.control_passed and self.decoy_passed

    @property
    def control_indices(self) -> tuple[int, ...]:
        return self.route.control_indices

    @property
    def message_indices(self) -> tuple[int, ...]:
        return self.route.message_indices

    @property
    def decoy_indices(self) -> tuple[int, ...]:
        return self.route.decoy_indices


@dataclass(frozen=True)
class BlockAttempt:
    block: TransportBlock
    attempt_index: int
    seed: int
    protocol: ProtocolBlockResult
    decode: Optional[TransportDecode]

    @property
    def status(self) -> AttemptStatus:
        if not self.protocol.accepted:
            return "protocol_rejected"
        if self.decode is not None and self.decode.recovered_bits is not None:
            return "recovered"
        return "uncorrectable"

    @property
    def recovered_bits(self) -> Optional[str]:
        return self.decode.recovered_bits if self.decode is not None else None


@dataclass(frozen=True)
class ProtocolResult:
    """Outcome for one logical payload, including selective retries."""

    frame: TransportFrame
    attempts: tuple[BlockAttempt, ...]
    blocks: tuple[BlockAttempt, ...]
    delivery_status: DeliveryStatus
    exhausted_blocks: tuple[int, ...]
    recovered_bits: Optional[str]

    @property
    def accepted(self) -> bool:
        return all(block.protocol.accepted for block in self.blocks)

    @property
    def payload_recovered(self) -> bool:
        return self.recovered_bits is not None

    @property
    def total_attempt_count(self) -> int:
        return len(self.attempts)

    @property
    def total_state_count(self) -> int:
        return sum(len(attempt.protocol.prepared_states) for attempt in self.attempts)


def simulate_qsdc(
    payload_bits: str,
    config: SimulatorConfig,
    backend: Optional[QSDCBackend] = None,
) -> ProtocolResult:
    """Transmit a logical payload through the configured Srikara protocol."""

    frame = encode_payload(payload_bits, config.error_correction)
    active_backend = backend or make_backend(config.backend, config.noise)
    attempts: list[BlockAttempt] = []
    final_blocks: list[BlockAttempt] = []

    for block in frame.blocks:
        final = _transmit_block(block, frame, config, active_backend, attempts)
        final_blocks.append(final)

    exhausted = tuple(
        attempt.block.index
        for attempt in final_blocks
        if attempt.recovered_bits is None
    )
    recovered = None
    if not exhausted:
        recovered = "".join(attempt.recovered_bits or "" for attempt in final_blocks)
        recovered = recovered[: frame.payload_bit_count]

    return ProtocolResult(
        frame=frame,
        attempts=tuple(attempts),
        blocks=tuple(final_blocks),
        delivery_status=_delivery_status(final_blocks, config.max_attempts_per_block),
        exhausted_blocks=exhausted,
        recovered_bits=recovered,
    )


def _transmit_block(
    block: TransportBlock,
    frame: TransportFrame,
    config: SimulatorConfig,
    backend: QSDCBackend,
    attempts: list[BlockAttempt],
) -> BlockAttempt:
    final: Optional[BlockAttempt] = None
    for attempt_index in range(config.max_attempts_per_block):
        seed = _attempt_seed(config.seed, block.index, attempt_index, frame)
        protocol = _run_protocol_block(
            block.symbols,
            config,
            backend,
            make_random_source(config.random_source, seed),
            seed,
        )
        decoded = None
        if protocol.accepted:
            decoded = decode_block(
                block,
                tuple(message.decoded_bits for message in protocol.messages),
                frame.error_correction,
            )
        final = BlockAttempt(block, attempt_index, seed, protocol, decoded)
        attempts.append(final)
        if final.recovered_bits is not None:
            break
    if final is None:
        raise RuntimeError("transport block was not attempted")
    return final


def _delivery_status(
    blocks: list[BlockAttempt],
    max_attempts: int,
) -> DeliveryStatus:
    failed = [block for block in blocks if block.recovered_bits is None]
    if not failed:
        return "recovered"
    if max_attempts > 1:
        return "retry_exhausted"
    if any(block.status == "protocol_rejected" for block in failed):
        return "protocol_rejected"
    return "uncorrectable"


def _attempt_seed(
    master_seed: int,
    block_index: int,
    attempt_index: int,
    frame: TransportFrame,
) -> int:
    if frame.error_correction == "none":
        return master_seed
    digest = hashlib.sha256()
    for part in (master_seed, block_index, attempt_index):
        encoded = str(part).encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
    return int.from_bytes(digest.digest()[:4], "big")


def _run_protocol_block(
    message_bits: tuple[str, ...],
    config: SimulatorConfig,
    backend: QSDCBackend,
    random_source: RandomSource,
    seed: int,
) -> ProtocolBlockResult:
    n_states = 4 * len(message_bits)
    backend.begin_run(seed)
    prepared_states = _bob_prepare_states(n_states, config, random_source)
    route = OpticalSwitch(random_source).route(n_states)
    transcript = build_transcript(route, random_source)

    controls = tuple(
        _check_state(prepared_states[index], backend, config, random_source, False)
        for index in route.control_indices
    )
    message_by_index = _encode_messages(
        route.message_indices,
        message_bits,
        config,
        random_source,
    )
    decoys = tuple(
        _check_state(prepared_states[index], backend, config, random_source, True)
        for index in route.decoy_indices
    )
    messages = tuple(
        _decode_message(
            prepared_states[index],
            message_by_index[index],
            backend,
            config,
            random_source,
        )
        for index in route.message_indices
    )

    return ProtocolBlockResult(
        backend_name=backend.name,
        random_source_name=random_source.name,
        check_tolerance_sigmas=config.tolerance_sigmas,
        intervals=config.intervals,
        check_axis_policy=config.check_axis_policy,
        message_axis_policy=config.message_axis_policy,
        measurement_noise_sigma=backend.measurement_noise_sigma,
        route=route,
        transcript=transcript,
        prepared_states=tuple(prepared_states),
        controls=controls,
        decoys=decoys,
        messages=messages,
    )


def _bob_prepare_states(
    n_states: int,
    config: SimulatorConfig,
    random_source: RandomSource,
) -> list[BobPreparedState]:
    return [
        BobPreparedState(
            index,
            config.alpha_distribution.sample(random_source),
            config.squeeze_r_distribution.sample(random_source),
            config.theta_distribution.sample(random_source),
        )
        for index in range(n_states)
    ]


def _encode_messages(
    indices: tuple[int, ...],
    message_bits: tuple[str, ...],
    config: SimulatorConfig,
    random_source: RandomSource,
) -> dict[int, tuple[str, float, complex]]:
    encoded = {}
    for index, bits in zip(indices, message_bits):
        value = sample_message_value(bits, random_source, intervals=config.intervals)
        encoded[index] = (bits, value, beta_for_message_value(value))
    return encoded


def _check_state(
    state: BobPreparedState,
    backend: QSDCBackend,
    config: SimulatorConfig,
    random_source: RandomSource,
    returned: bool,
) -> ChannelCheck:
    axis = _check_axis(state, config, random_source)
    expectation = (
        backend.returned_expectation(state.alpha, state.squeeze_r, state.theta, axis)
        if returned
        else backend.control_expectation(
            state.alpha,
            state.squeeze_r,
            state.theta,
            axis,
        )
    )
    measured = (
        backend.returned_measurement(
            state.alpha,
            state.squeeze_r,
            state.theta,
            beta=0j,
            axis=axis,
        )
        if returned
        else backend.control_measurement(
            state.alpha,
            state.squeeze_r,
            state.theta,
            axis,
        )
    )
    tolerance = config.tolerance_sigmas * expectation.sigma
    if not all(_finite(value) for value in (measured, expectation.mean, tolerance)):
        status: CheckStatus = "invalid_measurement"
    elif abs(float(measured) - expectation.mean) <= tolerance:
        status = "passed"
    else:
        status = "out_of_tolerance"
    return ChannelCheck(
        state.index,
        axis,
        expectation.mean,
        expectation.sigma,
        measured,
        status,
    )


def _check_axis(
    state: BobPreparedState,
    config: SimulatorConfig,
    random_source: RandomSource,
) -> QuadratureAxis:
    if config.check_axis_policy == "random":
        return random_source.choice((QuadratureAxis.Q, QuadratureAxis.P))
    return (
        QuadratureAxis.Q
        if abs(state.alpha.real) >= abs(state.alpha.imag)
        else QuadratureAxis.P
    )


def _decode_message(
    state: BobPreparedState,
    message: tuple[str, float, complex],
    backend: QSDCBackend,
    config: SimulatorConfig,
    random_source: RandomSource,
) -> MessageDecode:
    bits, message_value, alice_beta = message
    axis = _message_axis(state, backend, config, random_source)
    measured = backend.returned_measurement(
        state.alpha,
        state.squeeze_r,
        state.theta,
        beta=alice_beta,
        axis=axis,
    )
    baseline = backend.returned_expectation(
        state.alpha,
        state.squeeze_r,
        state.theta,
        axis,
    ).mean
    response = backend.message_response_factor(state.squeeze_r, state.theta, axis)
    if (
        not all(_finite(value) for value in (measured, baseline, response))
        or response == 0
    ):
        return MessageDecode(
            state.index,
            config.intervals,
            bits,
            message_value,
            alice_beta,
            axis,
            measured,
            baseline,
            None,
            response,
            None,
            None,
            "invalid_measurement",
        )

    observed_delta = float(measured) - baseline
    decoded_value = observed_delta / response
    if not isfinite(decoded_value):
        return MessageDecode(
            state.index,
            config.intervals,
            bits,
            message_value,
            alice_beta,
            axis,
            measured,
            baseline,
            observed_delta,
            response,
            None,
            None,
            "invalid_measurement",
        )
    return MessageDecode(
        state.index,
        config.intervals,
        bits,
        message_value,
        alice_beta,
        axis,
        measured,
        baseline,
        observed_delta,
        response,
        decoded_value,
        bits_for_real(decoded_value, intervals=config.intervals),
    )


def _message_axis(
    state: BobPreparedState,
    backend: QSDCBackend,
    config: SimulatorConfig,
    random_source: RandomSource,
) -> QuadratureAxis:
    if config.message_axis_policy == "random":
        return random_source.choice((QuadratureAxis.Q, QuadratureAxis.P))
    q_response = backend.message_response_factor(
        state.squeeze_r,
        state.theta,
        QuadratureAxis.Q,
    )
    p_response = backend.message_response_factor(
        state.squeeze_r,
        state.theta,
        QuadratureAxis.P,
    )
    return QuadratureAxis.Q if abs(q_response) >= abs(p_response) else QuadratureAxis.P


def _finite(value: Optional[float]) -> bool:
    return value is not None and isfinite(value)
