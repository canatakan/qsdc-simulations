"""First proposed Alice-Bob QSDC protocol from paper 11."""

from __future__ import annotations

from dataclasses import dataclass
from math import pi
from random import Random

from .backends import AnalyticBackend, QSDCBackend
from .encoding import beta_for_message_value, bits_for_real, sample_message_value
from .gaussian import displacement_after_unsqueeze


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
class ProtocolConfig:
    """Simulation settings for the first QSDC protocol."""

    n_states: int = 8
    alpha_bound: float = 2.0
    squeeze_r_min: float = 0.05
    squeeze_r_max: float = 0.8
    tolerance: float = 1e-7
    seed: int = 11


@dataclass(frozen=True)
class ProtocolResult:
    backend_name: str
    control_passed: bool
    decoy_passed: bool
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


def simulate_first_qsdc(
    message_bits: list[str] | tuple[str, ...],
    config: ProtocolConfig | None = None,
    backend: QSDCBackend | None = None,
) -> ProtocolResult:
    """Run the paper's first Alice-Bob QSDC protocol."""

    config = config or ProtocolConfig(n_states=4 * len(message_bits))
    active_backend: QSDCBackend = backend if backend is not None else AnalyticBackend()
    _validate_config(config, len(message_bits))
    active_backend.begin_run(config.seed)

    rng = Random(config.seed)
    prepared_states = _bob_prepare_states(config, rng)

    all_indices = list(range(config.n_states))
    rng.shuffle(all_indices)
    control_indices = tuple(sorted(all_indices[: config.n_states // 2]))
    remaining = all_indices[config.n_states // 2:]
    rng.shuffle(remaining)
    message_indices = tuple(sorted(remaining[: config.n_states // 4]))
    decoy_indices = tuple(sorted(remaining[config.n_states // 4:]))

    controls = tuple(
        _check_control(prepared_states[index], active_backend, config, rng)
        for index in control_indices
    )
    control_passed = all(check.passed for check in controls)

    message_by_index: dict[int, tuple[str, float, complex]] = {}
    for index, bits in zip(message_indices, message_bits):
        message_value = sample_message_value(bits, rng)
        beta = beta_for_message_value(message_value)
        message_by_index[index] = (bits, message_value, beta)

    decoys = tuple(
        _check_decoy(prepared_states[index], active_backend, config, rng)
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


def _validate_config(config: ProtocolConfig, message_count: int) -> None:
    if config.n_states % 4 != 0:
        raise ValueError("n_states must be divisible by 4")
    expected_messages = config.n_states // 4
    if message_count != expected_messages:
        raise ValueError(
            f"expected {expected_messages} 3-bit symbols for n={config.n_states}, "
            f"got {message_count}"
        )
    if config.squeeze_r_min < 0 or config.squeeze_r_max < config.squeeze_r_min:
        raise ValueError("invalid squeezing range")


def _bob_prepare_states(config: ProtocolConfig, rng: Random) -> list[BobPreparedState]:
    states: list[BobPreparedState] = []
    for index in range(config.n_states):
        alpha = complex(
            rng.uniform(-config.alpha_bound, config.alpha_bound),
            rng.uniform(-config.alpha_bound, config.alpha_bound),
        )
        squeeze_r = rng.uniform(config.squeeze_r_min, config.squeeze_r_max)
        theta = rng.uniform(0.0, 2.0 * pi)
        states.append(BobPreparedState(index, alpha, squeeze_r, theta))
    return states


def _check_control(
    state: BobPreparedState,
    backend: QSDCBackend,
    config: ProtocolConfig,
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
    state: BobPreparedState,
    backend: QSDCBackend,
    config: ProtocolConfig,
    rng: Random,
) -> DecoyCheck:
    axis = rng.choice(("q", "p"))
    expected = state.alpha.real if axis == "q" else state.alpha.imag
    measured = backend.returned_measurement(
        state.alpha, state.squeeze_r, state.theta, beta=0.0 + 0.0j, axis=axis
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
    rng: Random,
) -> MessageDecode:
    bits, message_value, alice_beta = message
    axis = _message_axis(state, rng)
    measured = backend.returned_measurement(
        state.alpha, state.squeeze_r, state.theta, beta=alice_beta, axis=axis
    )
    initial_component = state.alpha.real if axis == "q" else state.alpha.imag
    observed_delta = measured - initial_component
    response_factor = _message_response_factor(
        state.squeeze_r, state.theta, axis)
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


def _message_axis(state: BobPreparedState, rng: Random) -> str:
    q_factor = abs(_message_response_factor(state.squeeze_r, state.theta, "q"))
    p_factor = abs(_message_response_factor(state.squeeze_r, state.theta, "p"))
    if q_factor < 1e-12:
        return "p"
    if p_factor < 1e-12:
        return "q"
    return rng.choice(("q", "p"))


def _message_response_factor(squeeze_r: float, theta: float, axis: str) -> float:
    response = displacement_after_unsqueeze(1.0 + 1.0j, squeeze_r, theta)
    if axis == "q":
        return response.real
    if axis == "p":
        return response.imag
    raise ValueError(f"unknown quadrature axis {axis!r}")
