from __future__ import annotations

from dataclasses import dataclass
from math import pi

from srikara.simulator.backends import AnalyticBackend, QSDCBackend
from srikara.simulator.core.config import (
    ProtocolConfig,
    ResolvedProtocolConfig,
    resolve_config,
)
from srikara.simulator.core.encoding import (
    beta_for_message_value,
    bits_for_real,
    sample_message_value,
)
from srikara.simulator.core.flow import (
    ModeRoute,
    OpticalSwitch,
    ProtocolTranscript,
    build_transcript,
)
from utils import ClassicalRandomSource, RandomSource


@dataclass(frozen=True)
class BobPreparedState:
    """Bob's private state parameters for one time slot."""

    index: int
    alpha: complex
    squeeze_r: float
    theta: float


@dataclass(frozen=True)
class ControlCheck:
    index: int
    axis: str
    expected: float
    measured: float
    passed: bool


@dataclass(frozen=True)
class DecoyCheck:
    index: int
    axis: str
    expected: float
    measured: float
    passed: bool


@dataclass(frozen=True)
class MessageDecode:
    index: int
    sent_bits: str
    message_value: float
    alice_beta: complex
    axis: str
    measured: float
    observed_delta: float
    response_factor: float
    recovered_beta: complex
    decoded_value: float
    decoded_bits: str


@dataclass(frozen=True)
class ProtocolResult:
    backend_name: str
    random_source_name: str
    check_tolerance: float
    control_passed: bool
    decoy_passed: bool
    route: ModeRoute
    transcript: ProtocolTranscript
    prepared_states: tuple[BobPreparedState, ...]
    control_indices: tuple[int, ...]
    message_indices: tuple[int, ...]
    decoy_indices: tuple[int, ...]
    controls: tuple[ControlCheck, ...]
    decoys: tuple[DecoyCheck, ...]
    messages: tuple[MessageDecode, ...]

    @property
    def accepted(self) -> bool:
        return self.control_passed and self.decoy_passed


def simulate_qsdc(
    message_bits: list[str] | tuple[str, ...],
    config: ProtocolConfig | None = None,
    backend: QSDCBackend | None = None,
    random_source: RandomSource | None = None,
) -> ProtocolResult:
    config = config or ProtocolConfig(n_states=4 * len(message_bits))
    active_backend: QSDCBackend = backend if backend is not None else AnalyticBackend()
    resolved_config = resolve_config(config, active_backend, len(message_bits))
    protocol_random = random_source or ClassicalRandomSource(resolved_config.seed)

    # Backend seeding is only for backend-owned sampling, such as SF homodyne draws.
    active_backend.begin_run(resolved_config.seed)

    prepared_states = _bob_prepare_states(resolved_config, protocol_random)
    route = OpticalSwitch(protocol_random).route(resolved_config.n_states)
    transcript = build_transcript(route, protocol_random)

    controls = tuple(
        _check_control(
            prepared_states[index], active_backend, resolved_config, protocol_random
        )
        for index in route.control_indices
    )
    control_passed = all(check.passed for check in controls)

    message_by_index: dict[int, tuple[str, float, complex]] = {}
    for index, bits in zip(route.message_indices, message_bits):
        message_value = sample_message_value(bits, protocol_random)
        beta = beta_for_message_value(message_value)
        message_by_index[index] = (bits, message_value, beta)

    decoys = tuple(
        _check_decoy(
            prepared_states[index], active_backend, resolved_config, protocol_random
        )
        for index in route.decoy_indices
    )
    decoy_passed = all(check.passed for check in decoys)

    messages = tuple(
        _decode_message(
            prepared_states[index],
            message_by_index[index],
            active_backend,
            protocol_random,
        )
        for index in route.message_indices
    )

    return ProtocolResult(
        backend_name=active_backend.name,
        random_source_name=protocol_random.name,
        check_tolerance=resolved_config.tolerance,
        control_passed=control_passed,
        decoy_passed=decoy_passed,
        route=route,
        transcript=transcript,
        prepared_states=tuple(prepared_states),
        control_indices=route.control_indices,
        message_indices=route.message_indices,
        decoy_indices=route.decoy_indices,
        controls=controls,
        decoys=decoys,
        messages=messages,
    )


def _bob_prepare_states(
    config: ResolvedProtocolConfig, random_source: RandomSource
) -> list[BobPreparedState]:
    states: list[BobPreparedState] = []
    for index in range(config.n_states):
        alpha = complex(
            random_source.uniform(-config.alpha_bound, config.alpha_bound),
            random_source.uniform(-config.alpha_bound, config.alpha_bound),
        )
        squeeze_r = random_source.uniform(
            config.squeeze_r_min, config.squeeze_r_max)
        theta = random_source.uniform(0.0, 2.0 * pi)
        states.append(BobPreparedState(index, alpha, squeeze_r, theta))
    return states


def _check_control(
    state: BobPreparedState,
    backend: QSDCBackend,
    config: ResolvedProtocolConfig,
    random_source: RandomSource,
) -> ControlCheck:
    axis = random_source.choice(("q", "p"))
    expected = state.alpha.real if axis == "q" else state.alpha.imag
    measured = backend.control_measurement(
        state.alpha, state.squeeze_r, state.theta, axis
    )
    return ControlCheck(
        index=state.index,
        axis=axis,
        expected=expected,
        measured=measured,
        passed=abs(measured - expected) <= config.tolerance,
    )


def _check_decoy(
    state: BobPreparedState,
    backend: QSDCBackend,
    config: ResolvedProtocolConfig,
    random_source: RandomSource,
) -> DecoyCheck:
    axis = random_source.choice(("q", "p"))
    expected = state.alpha.real if axis == "q" else state.alpha.imag
    measured = backend.returned_measurement(
        state.alpha, state.squeeze_r, state.theta, beta=0j, axis=axis
    )
    return DecoyCheck(
        index=state.index,
        axis=axis,
        expected=expected,
        measured=measured,
        passed=abs(measured - expected) <= config.tolerance,
    )


def _decode_message(
    state: BobPreparedState,
    message: tuple[str, float, complex],
    backend: QSDCBackend,
    random_source: RandomSource,
) -> MessageDecode:
    bits, message_value, alice_beta = message
    axis = _message_axis(random_source)
    measured = backend.returned_measurement(
        state.alpha, state.squeeze_r, state.theta, beta=alice_beta, axis=axis
    )
    initial_component = state.alpha.real if axis == "q" else state.alpha.imag
    observed_delta = measured - initial_component
    response_factor = backend.message_response_factor(
        state.squeeze_r, state.theta, axis
    )
    decoded_value = observed_delta / response_factor
    recovered_beta = complex(decoded_value, decoded_value)
    decoded_bits = bits_for_real(decoded_value)
    return MessageDecode(
        index=state.index,
        sent_bits=bits,
        message_value=message_value,
        alice_beta=alice_beta,
        axis=axis,
        measured=measured,
        observed_delta=observed_delta,
        response_factor=response_factor,
        recovered_beta=recovered_beta,
        decoded_value=decoded_value,
        decoded_bits=decoded_bits,
    )


def _message_axis(random_source: RandomSource) -> str:
    return random_source.choice(("q", "p"))
