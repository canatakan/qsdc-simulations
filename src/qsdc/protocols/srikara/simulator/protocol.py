from __future__ import annotations

from dataclasses import dataclass
from math import pi, sqrt

from qsdc.common import transmission
from qsdc.common.quadrature import P, Q, Quadrature
from qsdc.common.random import RandomSource, make_random_source

from ..config import SimulatorConfig
from ..constants import MESSAGE_DIRECTION, STATES_PER_SYMBOL, VACUUM_VARIANCE
from .backends import Backend, Expectation, PreparedState, make_backend
from .encoding import INTERVAL_CODES
from .routing import ModeRoute, route_modes
from .transport import Block, decode_block, encode_blocks

AXES = (Q, P)


@dataclass(frozen=True)
class Check:
    index: int
    axis: Quadrature
    expected: float
    sigma: float
    measured: float
    passed: bool


@dataclass(frozen=True)
class Message:
    index: int
    sent_bits: str
    value: float
    axis: Quadrature
    measured: float
    baseline: float
    response: float
    decoded_value: float
    decoded_bits: str

    @property
    def correct(self) -> bool:
        return self.decoded_bits == self.sent_bits


@dataclass(frozen=True)
class BlockRun:
    states: tuple[PreparedState, ...]
    route: ModeRoute
    controls: tuple[Check, ...]
    decoys: tuple[Check, ...]
    messages: tuple[Message, ...]

    @property
    def aborted(self) -> bool:
        return not all(check.passed for check in self.controls)

    @property
    def accepted(self) -> bool:
        return all(check.passed for check in self.controls + self.decoys)


Attempt = transmission.Attempt[Block, BlockRun]
Transmission = transmission.Transmission[Block, BlockRun]


class SrikaraSimulator:
    def __init__(self, config: SimulatorConfig, backend: Backend | None = None):
        self.config = config
        self.backend = backend or make_backend(config)
        self.code = INTERVAL_CODES[config.intervals]

    def transmit(self, payload: str) -> Transmission:
        if not payload or set(payload) - {"0", "1"}:
            raise ValueError("payload must be a non-empty string of 0s and 1s")

        config = self.config
        return transmission.send_blocks(
            encode_blocks(payload, config.error_correction),
            config.seed,
            config.max_attempts,
            self.send_block,
        )

    def send_block(self, block: Block, seed: int) -> tuple[BlockRun, str | None]:
        rng = make_random_source(self.config.random_source, seed)
        self.backend.begin_run(seed)
        symbols = block.symbols

        # 1. Bob prepares squeezed coherent states with random alpha, r and theta.
        states = self.prepare_states(STATES_PER_SYMBOL * len(symbols), rng)

        # 2. Alice splits the states into controls, messages and decoys.
        route = route_modes(len(states), rng)

        # 3. Bob reveals alpha and s of the controls, and Alice checks them.
        controls = self.check_controls(states, route.control, rng)
        run = BlockRun(states, route, controls, (), ())
        if run.aborted:
            return run, None

        # 4. Alice encodes each symbol as a value m from its interval.
        values = [self.code.sample(bits, rng) for bits in symbols]

        # 5. Alice sends the decoys back unchanged, and Bob checks them.
        decoys = self.check_decoys(states, route.decoy, rng)

        # 6. Alice displaces each message state by m(1 + i), and Bob decodes m.
        messages = self.receive_messages(states, route.message, symbols, values, rng)
        run = BlockRun(states, route, controls, decoys, messages)
        if not run.accepted:
            return run, None

        # 7. Bob corrects the received symbols with the block's code.
        received = [message.decoded_bits for message in messages]
        return run, decode_block(block, received, self.config.error_correction)

    def prepare_states(
        self, count: int, rng: RandomSource
    ) -> tuple[PreparedState, ...]:
        config = self.config
        sigma = sqrt(config.alpha_variance_snu * VACUUM_VARIANCE)

        states = []
        for index in range(count):
            alpha = complex(rng.gauss(sigma), rng.gauss(sigma))
            squeeze_r = config.squeeze_r.sample(rng)
            theta = pi * config.theta_pi.sample(rng)
            states.append(PreparedState(index, alpha, squeeze_r, theta))

        return tuple(states)

    def check_controls(
        self,
        states: tuple[PreparedState, ...],
        indices: tuple[int, ...],
        rng: RandomSource,
    ) -> tuple[Check, ...]:
        # Alice unsqueezes each control and measures q or p at random.
        checks = []
        for i in indices:
            state, axis = states[i], rng.choice(AXES)
            expected = self.backend.expect_control(state, axis)
            measured = self.backend.measure_control(state, axis)
            checks.append(self.compare(state, axis, expected, measured))

        return tuple(checks)

    def check_decoys(
        self,
        states: tuple[PreparedState, ...],
        indices: tuple[int, ...],
        rng: RandomSource,
    ) -> tuple[Check, ...]:
        # Bob unsqueezes each decoy and measures q or p at random.
        checks = []
        for i in indices:
            state, axis = states[i], rng.choice(AXES)
            expected = self.backend.expect_returned(state, axis)
            measured = self.backend.measure_returned(state, axis)
            checks.append(self.compare(state, axis, expected, measured))

        return tuple(checks)

    def compare(
        self,
        state: PreparedState,
        axis: Quadrature,
        expected: Expectation,
        measured: float,
    ) -> Check:
        # A check passes within tolerance_sigmas of its expected value.
        tolerance = self.config.tolerance_sigmas * expected.sigma
        passed = abs(measured - expected.mean) <= tolerance

        return Check(state.index, axis, expected.mean, expected.sigma, measured, passed)

    def receive_messages(
        self,
        states: tuple[PreparedState, ...],
        indices: tuple[int, ...],
        symbols: tuple[str, ...],
        values: list[float],
        rng: RandomSource,
    ) -> tuple[Message, ...]:
        messages = []
        for i, bits, value in zip(indices, symbols, values):
            messages.append(self.receive_message(states[i], bits, value, rng))

        return tuple(messages)

    def receive_message(
        self, state: PreparedState, bits: str, value: float, rng: RandomSource
    ) -> Message:
        axis = self.message_axis(state, rng)

        measured = self.backend.measure_returned(state, axis, value * MESSAGE_DIRECTION)
        baseline = self.backend.expect_returned(state, axis).mean
        response = self.backend.message_response(state, axis)

        # Without any signal reaching Bob, his best guess is m = 0.
        decoded = (measured - baseline) / response if response else 0.0

        return Message(
            state.index,
            bits,
            value,
            axis,
            measured,
            baseline,
            response,
            decoded,
            self.code.decode(decoded),
        )

    def message_axis(self, state: PreparedState, rng: RandomSource) -> Quadrature:
        policy = self.config.axis_policy

        if policy == "random":
            return rng.choice(AXES)

        response_q = self.backend.message_response(state, Q)
        response_p = self.backend.message_response(state, P)

        if policy == "best_qp":
            return Q if abs(response_q) >= abs(response_p) else P

        # aligned: along the message displacement Bob sees after unsqueezing.
        return Quadrature(complex(response_q, response_p))
