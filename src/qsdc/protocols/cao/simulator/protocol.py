from __future__ import annotations

from dataclasses import dataclass, replace
from math import exp, sqrt

from qsdc.common import transmission
from qsdc.common.random import make_random_source
from qsdc.protocols.cao.config import SimulatorConfig
from qsdc.protocols.cao.constants import EPR_BOUND
from qsdc.protocols.cao.simulator.backends import AnalyticBackend
from qsdc.protocols.cao.simulator.mapping import (
    Box,
    interval_code,
    map_box,
    restore_block,
    restore_message,
    uniformize_block,
    uniformize_message,
)
from qsdc.protocols.cao.simulator.postprocessing import (
    Estimate,
    confidences,
    estimate,
    reconcile,
    reconciliation_code,
)


@dataclass(frozen=True)
class Block(transmission.Block):
    uniformized: str


def encode_blocks(payload: str, block_bits: int) -> list[Block]:
    padded = payload.ljust(-(-len(payload) // block_bits) * block_bits, "0")
    uniformized = uniformize_message(padded)
    return [
        Block(i, payload[i : i + block_bits], uniformized[2 * i : 2 * (i + block_bits)])
        for i in range(0, len(payload), block_bits)
    ]


@dataclass(frozen=True)
class Check:
    index: int
    alice: complex
    bob: complex

    @property
    def statistic(self) -> float:
        x = (self.alice.real - self.bob.real) / sqrt(2)
        p = (self.alice.imag + self.bob.imag) / sqrt(2)
        return x * x + p * p

    @property
    def passed(self) -> bool:
        return self.statistic < EPR_BOUND


@dataclass(frozen=True)
class Stage:
    checks: tuple[Check, ...]
    expected_failure_rate: float
    threshold: float

    @property
    def failure_rate(self) -> float:
        return sum(not check.passed for check in self.checks) / len(self.checks)

    @property
    def accepted(self) -> bool:
        return self.failure_rate < self.threshold


@dataclass(frozen=True)
class Signal:
    index: int
    box: Box
    g1: float
    g2: float
    measured: complex
    decoded_value: float
    decoded_bits: str

    @property
    def detection_valid(self) -> bool:
        return self.box.detection_matches(self.decoded_bits)

    @property
    def parity_valid(self) -> bool:
        return self.box.parity_matches(self.decoded_bits)

    @property
    def valid(self) -> bool:
        return self.detection_valid and self.parity_valid

    @property
    def decoded_payload(self) -> str:
        return self.box.unmap(self.decoded_bits)


@dataclass(frozen=True)
class BlockRun:
    pairs: int
    channel: Stage
    authentication: Stage | None
    signals: tuple[Signal, ...] = ()
    estimate: Estimate | None = None
    syndrome: str | None = None
    reconciled: str | None = None

    @property
    def accepted(self) -> bool:
        return self.authentication is not None and self.authentication.accepted


Attempt = transmission.Attempt[Block, BlockRun]
Transmission = transmission.Transmission[Block, BlockRun]


class Simulator:
    def __init__(self, config: SimulatorConfig, backend: AnalyticBackend | None = None):
        self.config = config
        self.backend = backend or AnalyticBackend(config.squeeze_r, config.noise)
        self.code = interval_code(config)
        self.expected_failure_rate = exp(
            -EPR_BOUND / (2 * self.backend.check_variance())
        )
        rate = self.expected_failure_rate
        margin = sqrt(rate * (1 - rate) / config.check_pairs)
        self.check_threshold = rate + config.check_tolerance_sigmas * margin
        self.reconciliation = (
            reconciliation_code(config) if config.reconciliation else None
        )

    def transmit(self, payload: str) -> Transmission:
        config = self.config
        return transmission.send_blocks(
            encode_blocks(payload, config.block_bits),
            config.seed,
            config.max_attempts,
            self._send,
        )

    def _send(self, block: Block, seed: int) -> tuple[BlockRun, str | None]:
        run = self.run_block(block, seed)
        if not run.accepted:
            return run, None
        if self.reconciliation is None:
            if not all(signal.valid for signal in run.signals):
                return run, None
            payload = "".join(signal.decoded_payload for signal in run.signals)
        elif run.reconciled is None:
            return run, None
        else:
            payload = run.reconciled
        return run, restore_message(restore_block(payload))[: len(block.bits)]

    def run_block(self, block: Block, seed: int) -> BlockRun:
        config = self.config
        rng = make_random_source(config.random_source, seed)
        self.backend.begin_run(seed)

        checks = config.check_pairs
        pairs = 2 * checks + config.boxes
        positions = rng.shuffled(range(pairs))
        channel_positions = sorted(positions[:checks])
        authentication_positions = sorted(positions[checks : 2 * checks])
        signal_positions = sorted(positions[2 * checks :])

        channel = self._stage(channel_positions)
        if not channel.accepted:
            return BlockRun(pairs, channel, None)
        authentication = self._stage(authentication_positions)
        if not authentication.accepted:
            return BlockRun(pairs, channel, authentication)

        bits = uniformize_block(block.uniformized, rng)
        width = config.box_bits
        boxes = [
            map_box(bits[i : i + width], config.detection_bits, rng)
            for i in range(0, len(bits), width)
        ]
        sigma = sqrt(config.modulation_variance_snu)
        g1 = [self.code.sample(box.bits, rng) for box in boxes]
        g2 = [rng.gauss(sigma) for _ in boxes]
        measured = []
        for x, p in zip(g1, g2):
            measured.append(self.backend.measure_signal(complex(x, p)))

        channel_estimate = estimate(g2, [m.imag for m in measured])
        signals = []
        for i, box in enumerate(boxes):
            value = measured[i].real / channel_estimate.gain
            signals.append(
                Signal(
                    index=signal_positions[i],
                    box=box,
                    g1=g1[i],
                    g2=g2[i],
                    measured=measured[i],
                    decoded_value=value,
                    decoded_bits=self.code.decode(value),
                )
            )
        run = BlockRun(pairs, channel, authentication, tuple(signals), channel_estimate)
        if self.reconciliation is None:
            return run

        values = [signal.decoded_value for signal in signals]
        bit_confidences = confidences(boxes, values, self.code, channel_estimate)
        syndrome, reconciled = reconcile(
            self.reconciliation,
            boxes,
            bit_confidences,
            config.reconciliation.max_iterations,
        )
        return replace(run, syndrome=syndrome, reconciled=reconciled)

    def _stage(self, positions: list[int]) -> Stage:
        checks = tuple(
            Check(index, *self.backend.measure_check()) for index in positions
        )
        return Stage(checks, self.expected_failure_rate, self.check_threshold)
