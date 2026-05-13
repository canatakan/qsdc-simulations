"""CV QSDC protocol from paper 11."""

from __future__ import annotations

from dataclasses import dataclass
from math import pi
from random import Random

from simulator.backends import AnalyticBackend, QSDCBackend
from .config import ProtocolConfig, ResolvedProtocolConfig, resolve_config
from .encoding import beta_for_message_value, bits_for_real, sample_message_value


@dataclass(frozen=True)
class PreparedState:
    """Private state parameters for one time slot."""

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
    message_beta: complex
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
    check_tolerance: float
    control_passed: bool
    decoy_passed: bool
    prepared_states: tuple[PreparedState, ...]
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
) -> ProtocolResult:
    """Run the CV QSDC protocol."""

    config = config or ProtocolConfig(n_states=4 * len(message_bits))
    active_backend: QSDCBackend = backend if backend is not None else AnalyticBackend()
    resolved_config = resolve_config(config, active_backend, len(message_bits))
    active_backend.begin_run(resolved_config.seed)

    rng = Random(resolved_config.seed)
    prepared_states = _prepare_states(resolved_config, rng)

    all_indices = list(range(resolved_config.n_states))
    rng.shuffle(all_indices)
    control_indices = tuple(sorted(all_indices[: resolved_config.n_states // 2]))
    remaining = all_indices[resolved_config.n_states // 2:]
    rng.shuffle(remaining)
    message_indices = tuple(sorted(remaining[: resolved_config.n_states // 4]))
    decoy_indices = tuple(sorted(remaining[resolved_config.n_states // 4:]))

    controls = tuple(
        _check_control(prepared_states[index], active_backend, resolved_config, rng)
        for index in control_indices
    )
    control_passed = all(check.passed for check in controls)

    message_by_index: dict[int, tuple[str, float, complex]] = {}
    for index, bits in zip(message_indices, message_bits):
        message_value = sample_message_value(bits, rng)
        beta = beta_for_message_value(message_value)
        message_by_index[index] = (bits, message_value, beta)

    decoys = tuple(
        _check_decoy(prepared_states[index], active_backend, resolved_config, rng)
        for index in decoy_indices
    )
    decoy_passed = all(check.passed for check in decoys)

    messages = tuple(
        _decode_message(
            prepared_states[index],
            message_by_index[index],
            active_backend,
            rng,
        )
        for index in message_indices
    )

    return ProtocolResult(
        backend_name=active_backend.name,
        check_tolerance=resolved_config.tolerance,
        control_passed=control_passed,
        decoy_passed=decoy_passed,
        prepared_states=tuple(prepared_states),
        control_indices=control_indices,
        message_indices=message_indices,
        decoy_indices=decoy_indices,
        controls=controls,
        decoys=decoys,
        messages=messages,
    )


def _prepare_states(
    config: ResolvedProtocolConfig, rng: Random
) -> list[PreparedState]:
    states: list[PreparedState] = []
    for index in range(config.n_states):
        alpha = complex(
            rng.uniform(-config.alpha_bound, config.alpha_bound),
            rng.uniform(-config.alpha_bound, config.alpha_bound),
        )
        squeeze_r = rng.uniform(config.squeeze_r_min, config.squeeze_r_max)
        theta = rng.uniform(0.0, 2.0 * pi)
        states.append(PreparedState(index, alpha, squeeze_r, theta))
    return states


def _check_control(
    state: PreparedState,
    backend: QSDCBackend,
    config: ResolvedProtocolConfig,
    rng: Random,
) -> ControlCheck:
    axis = rng.choice(("q", "p"))
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
    state: PreparedState,
    backend: QSDCBackend,
    config: ResolvedProtocolConfig,
    rng: Random,
) -> DecoyCheck:
    axis = rng.choice(("q", "p"))
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
    state: PreparedState,
    message: tuple[str, float, complex],
    backend: QSDCBackend,
    rng: Random,
) -> MessageDecode:
    bits, message_value, message_beta = message
    axis = _message_axis(rng)
    measured = backend.returned_measurement(
        state.alpha, state.squeeze_r, state.theta, beta=message_beta, axis=axis
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
        message_beta=message_beta,
        axis=axis,
        measured=measured,
        observed_delta=observed_delta,
        response_factor=response_factor,
        recovered_beta=recovered_beta,
        decoded_value=decoded_value,
        decoded_bits=decoded_bits,
    )


def _message_axis(rng: Random) -> str:
    return rng.choice(("q", "p"))
