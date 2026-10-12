from __future__ import annotations

from dataclasses import dataclass
from math import pi, sqrt

from qsdc.common.quadrature import VACUUM_VARIANCE, P, Q, Quadrature
from qsdc.common.random import RandomSource, derive_seed, make_random_source
from qsdc.protocols.srikara.config import SimulatorConfig
from qsdc.protocols.srikara.simulator.backends import (
    Backend,
    PreparedState,
    make_backend,
)
from qsdc.protocols.srikara.simulator.encoding import INTERVAL_CODES, MESSAGE_DIRECTION
from qsdc.protocols.srikara.simulator.routing import ModeRoute, route_modes
from qsdc.protocols.srikara.simulator.transport import (
    Block,
    decode_block,
    encode_blocks,
)

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


@dataclass(frozen=True)
class Attempt:
    block: Block
    number: int
    run: BlockRun
    decoded_bits: str | None


@dataclass(frozen=True)
class Transmission:
    attempts: tuple[Attempt, ...]

    @property
    def final_attempts(self) -> list[Attempt]:
        return list(
            {attempt.block.offset: attempt for attempt in self.attempts}.values()
        )

    @property
    def recovered_bits(self) -> str | None:
        decoded = [attempt.decoded_bits for attempt in self.final_attempts]
        return None if None in decoded else "".join(decoded)


class SrikaraSimulator:
    def __init__(self, config: SimulatorConfig, backend: Backend | None = None):
        self.config = config
        self.backend = backend or make_backend(config)
        self.code = INTERVAL_CODES[config.intervals]

    def transmit(self, payload: str) -> Transmission:
        if not payload or set(payload) - {"0", "1"}:
            raise ValueError("payload must be a non-empty string of 0s and 1s")
        config = self.config
        attempts = []
        for block_index, block in enumerate(
            encode_blocks(payload, config.error_correction)
        ):
            for number in range(config.max_attempts):
                seed = derive_seed(config.seed, block_index, number)
                run = self.run_block(block.symbols, seed)
                received = [message.decoded_bits for message in run.messages]
                decoded = None
                if run.accepted:
                    decoded = decode_block(block, received, config.error_correction)
                attempts.append(Attempt(block, number, run, decoded))
                if decoded is not None:
                    break
        return Transmission(tuple(attempts))

    def run_block(self, symbols: tuple[str, ...], seed: int) -> BlockRun:
        config = self.config
        rng = make_random_source(config.random_source, seed)
        self.backend.begin_run(seed)

        n_states = 4 * len(symbols)
        sigma = sqrt(config.alpha_variance_snu * VACUUM_VARIANCE)
        states = tuple(
            PreparedState(
                index,
                complex(rng.gauss(sigma), rng.gauss(sigma)),
                config.squeeze_r.sample(rng),
                pi * config.theta_pi.sample(rng),
            )
            for index in range(n_states)
        )
        route = route_modes(n_states, rng)
        controls = tuple(
            self._check(states[i], rng.choice(AXES), returned=False)
            for i in route.control
        )
        run = BlockRun(states, route, controls, (), ())
        if run.aborted:
            return run
        values = [self.code.sample(bits, rng) for bits in symbols]
        decoys = tuple(
            self._check(states[i], rng.choice(AXES), returned=True) for i in route.decoy
        )
        messages = tuple(
            self._message(states[i], bits, value, rng)
            for i, bits, value in zip(route.message, symbols, values)
        )
        return BlockRun(states, route, controls, decoys, messages)

    def _check(self, state: PreparedState, axis: Quadrature, returned: bool) -> Check:
        if returned:
            expected = self.backend.expect_returned(state, axis)
            measured = self.backend.measure_returned(state, axis)
        else:
            expected = self.backend.expect_control(state, axis)
            measured = self.backend.measure_control(state, axis)
        passed = (
            abs(measured - expected.mean)
            <= self.config.tolerance_sigmas * expected.sigma
        )
        return Check(state.index, axis, expected.mean, expected.sigma, measured, passed)

    def _message(
        self, state: PreparedState, bits: str, value: float, rng: RandomSource
    ) -> Message:
        if self.config.axis_policy == "random":
            axis = rng.choice(AXES)
        else:
            response_q = self.backend.message_response(state, Q)
            response_p = self.backend.message_response(state, P)
            if self.config.axis_policy == "best_qp":
                axis = Q if abs(response_q) >= abs(response_p) else P
            else:
                axis = Quadrature(complex(response_q, response_p))
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
