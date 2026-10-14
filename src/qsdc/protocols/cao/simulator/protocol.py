from __future__ import annotations

from dataclasses import dataclass, replace
from math import sqrt

from qsdc.common.coding.intervals import IntervalCode
from qsdc.common.random import RandomSource, derive_seed, make_random_source
from qsdc.common.transmission import BaseAttempt, BaseRun, BaseSimulator

from ..config import SimulatorConfig
from .backends import Backend, make_backend
from .blocks import Block
from .checks import Check, Checks
from .mapping import Box, interval_code
from .postprocessing import Estimate, Postprocessor
from .signals import Receiver, Signal


@dataclass(frozen=True)
class Positions:
    count: int
    channel: list[int]
    authentication: list[int]
    signal: list[int]


@dataclass(frozen=True)
class Run(BaseRun[Block]):
    signals: tuple[Signal, ...] = ()
    estimate: Estimate | None = None
    syndrome: str | None = None
    reconciled: str | None = None


@dataclass(frozen=True)
class Attempt(BaseAttempt[Run]):
    positions: Positions
    channel: tuple[Check, ...]
    authentication: tuple[Check, ...] = ()

    @property
    def pairs(self) -> int:
        return self.positions.count


class Simulator(BaseSimulator[Block, Attempt]):
    config: SimulatorConfig
    backend: Backend
    code: IntervalCode
    checks: Checks
    receiver: Receiver
    postprocessor: Postprocessor

    def __init__(self, config: SimulatorConfig, backend: Backend | None = None):
        self.config = config
        self.backend = backend or make_backend(config)
        self.code = interval_code(config)
        self.checks = Checks(self.backend, config.check_tolerance_sigmas)
        self.receiver = Receiver(self.backend, self.code)
        self.postprocessor = Postprocessor(config, self.code)

    def encode(self, payload: str) -> list[Block]:
        # With privacy amplification, each block becomes a random payload whose
        # hash is the message. Without it, the message is uniformized.
        config, amplifier = self.config, self.postprocessor.amplifier
        if amplifier is None:
            return Block.encode(payload, config.block_bits)

        seed = derive_seed(config.seed, "privacy amplification")
        rng = make_random_source(config.random_source, seed)
        return Block.amplify(payload, amplifier, rng)

    def run_attempt(self, blocks: list[Block], number: int, seed: int) -> Attempt:
        rng = make_random_source(self.config.random_source, seed)
        self.backend.prepare_run(seed)
        runs = tuple(Run(block, None) for block in blocks)

        # 1. Preparation: Alice prepares the EPR pairs, keeps S1 and sends S2.
        # Each pair goes at random to one of the two checks or to a box.
        positions = self.prepare_pairs(len(blocks), rng)
        # 2. Channel detection: both heterodyne a random group of pairs.
        channel = self.checks.measure(positions.channel)

        channel_test = self.checks.judge(channel)
        attempt = Attempt(number, (channel_test,), runs, positions, channel)
        if not channel_test.passed:
            return attempt

        # 3. Authentication: the same check on another group, published by Bob.
        authentication = self.checks.measure(positions.authentication)

        authentication_test = self.checks.judge(authentication)
        tests = (channel_test, authentication_test)
        attempt = replace(attempt, security_tests=tests, authentication=authentication)
        if not authentication_test.passed:
            return attempt

        count = self.config.boxes
        decoded = []
        for i, run in enumerate(runs):
            signal_positions = positions.signal[i * count : (i + 1) * count]
            # 4. Gaussian mapping: Alice maps the block onto boxes and draws G1'.
            boxes = run.block.boxes(self.config, rng)
            g1 = [self.code.sample(box.bits, rng) for box in boxes]
            # 5. Gaussian modulation: Alice displaces S1 by G1' in x and G2 in p.
            displacements = self.modulate(g1, rng)
            # 6. Measurement: Bob measures S_info jointly with S2.
            measured = self.receiver.measure(displacements)
            # 7. Postprocessing: parameter estimation, reconciliation and privacy
            # amplification.
            decoded.append(
                self.postprocess(run, signal_positions, boxes, displacements, measured)
            )

        return replace(attempt, runs=tuple(decoded))

    def prepare_pairs(self, blocks: int, rng: RandomSource) -> Positions:
        checks = blocks * self.config.check_pairs
        count = 2 * checks + blocks * self.config.boxes
        shuffled = rng.shuffled(range(count))

        return Positions(
            count,
            channel=sorted(shuffled[:checks]),
            authentication=sorted(shuffled[checks : 2 * checks]),
            signal=sorted(shuffled[2 * checks :]),
        )

    def modulate(self, g1: list[float], rng: RandomSource) -> list[complex]:
        sigma = sqrt(self.config.modulation_variance_snu)
        g2 = [rng.gauss(sigma) for _ in g1]

        return [complex(x, p) for x, p in zip(g1, g2)]

    def postprocess(
        self,
        run: Run,
        positions: list[int],
        boxes: list[Box],
        displacements: list[complex],
        measured: list[complex],
    ) -> Run:
        # 7a. Parameter estimation: Alice reveals G2, and Bob fits his gain.
        estimate = self.receiver.estimate(displacements, measured)
        run = replace(run, estimate=estimate)
        if not estimate.gain:
            return run

        signals = self.receiver.decode(
            positions, boxes, displacements, measured, estimate
        )
        run = replace(run, signals=signals)

        if self.config.reconciliation is None:
            # 7b. Without reconciliation, the paper's mapping restores the block.
            message = run.block.restore(signals)
        else:
            # 7b. Reconciliation, then 7c. privacy amplification.
            values = [signal.decoded_value for signal in signals]
            syndrome, reconciled = self.postprocessor.correct(boxes, values, estimate)
            run = replace(run, syndrome=syndrome, reconciled=reconciled)
            message = self.postprocessor.amplify(reconciled)

        if message is None:
            return run
        return replace(run, decoded_bits=message[: len(run.block.bits)])
