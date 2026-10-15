from __future__ import annotations

from dataclasses import dataclass, replace
from math import pi, sqrt

from qsdc.common.coding.intervals import IntervalCode
from qsdc.common.coding.ldpc import LdpcCode
from qsdc.common.random import RandomSource, make_random_source
from qsdc.common.transmission import BaseAttempt, BaseRun, BaseSimulator

from ..config import SimulatorConfig
from ..constants import INTERVAL_CODES, STATES_PER_SYMBOL, VACUUM_VARIANCE
from .backends import Backend, PreparedState, make_backend
from .blocks import Block, CodingOptions
from .checks import Check, Checks
from .messages import Message, Receiver
from .routing import ModeRoute


@dataclass(frozen=True)
class Run(BaseRun[Block]):
    messages: tuple[Message, ...] = ()


@dataclass(frozen=True)
class Attempt(BaseAttempt[Run]):
    states: tuple[PreparedState, ...]
    route: ModeRoute
    controls: tuple[Check, ...]
    decoys: tuple[Check, ...] = ()

    @property
    def symbols(self) -> list[str]:
        return [bits for run in self.runs for bits in run.block.symbols]


class Simulator(BaseSimulator[Block, Attempt]):
    config: SimulatorConfig
    backend: Backend
    code: IntervalCode
    checks: Checks
    receiver: Receiver

    def __init__(self, config: SimulatorConfig, backend: Backend | None = None):
        self.config = config
        self.backend = backend or make_backend(config)
        self.code = INTERVAL_CODES[config.intervals]
        self.checks = Checks(self.backend, config.tolerance_sigmas)
        self.receiver = Receiver(self.backend, self.code, config.axis_policy)

        self.ldpc = None
        if config.error_correction == "ldpc":
            settings = config.ldpc
            self.ldpc = LdpcCode.systematic(
                settings.data_bits,
                settings.parity_bits,
                settings.column_weight,
                settings.seed,
            )

    def encode(self, payload: str) -> list[Block]:
        if self.ldpc is None:
            return Block.encode(payload, self.config.error_correction)

        return Block.encode(
            payload, self.config.error_correction, CodingOptions(ldpc=self.ldpc)
        )

    def run_attempt(self, blocks: list[Block], number: int, seed: int) -> Attempt:
        rng = make_random_source(self.config.random_source, seed)
        self.backend.prepare_run(seed)

        runs = tuple(Run(block, None) for block in blocks)
        symbols = [bits for block in blocks for bits in block.symbols]

        # 1. Bob prepares squeezed coherent states with random alpha, r and theta.
        states = self.prepare_states(STATES_PER_SYMBOL * len(symbols), rng)
        # 2. Alice splits the states into controls, messages and decoys.
        route = ModeRoute.create(len(states), rng)
        # 3. Bob reveals alpha and s of the controls, and Alice checks them.
        controls = self.checks.controls(states, route.control, rng)

        control_test = self.checks.judge(controls)
        attempt = Attempt(number, (control_test,), runs, states, route, controls)
        if not control_test.passed:
            return attempt

        # 4. Alice encodes each symbol as a value m from its interval.
        values = [self.code.sample(bits, rng) for bits in symbols]
        # 5. Alice sends the decoys back unchanged, and Bob checks them.
        decoys = self.checks.decoys(states, route.decoy, rng)
        # 6. Alice displaces each message state by m(1 + i), and Bob decodes m.
        runs = self.receive_messages(attempt, values, rng)

        decoy_test = self.checks.judge(decoys)
        tests = (control_test, decoy_test)
        attempt = replace(attempt, security_tests=tests, runs=runs, decoys=decoys)
        if not decoy_test.passed:
            return attempt

        # 7. Bob corrects the received symbols of each block with its code.
        return replace(attempt, runs=tuple(self.correct(run) for run in runs))

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

    def receive_messages(
        self, attempt: Attempt, values: list[float], rng: RandomSource
    ) -> tuple[Run, ...]:
        messages = self.receiver.receive(
            attempt.states, attempt.route.message, attempt.symbols, values, rng
        )

        # The message states carry the symbols of the blocks in order.
        runs = []
        start = 0
        for run in attempt.runs:
            end = start + len(run.block.symbols)
            runs.append(replace(run, messages=messages[start:end]))
            start = end

        return tuple(runs)

    def correct(self, run: Run) -> Run:
        received = [message.decoded_bits for message in run.messages]

        if self.ldpc is not None:
            confidences = [
                confidence
                for message in run.messages
                for confidence in message.confidences(self.code)
            ]

            bits = run.block.decode(
                received,
                self.config.error_correction,
                CodingOptions(
                    ldpc=self.ldpc,
                    confidences=confidences,
                    max_iterations=self.config.ldpc.max_iterations,
                ),
            )
        else:
            bits = run.block.decode(received, self.config.error_correction)

        return replace(run, decoded_bits=bits)
