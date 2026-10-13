from __future__ import annotations

from dataclasses import dataclass, replace
from math import exp, sqrt

from qsdc.common import transmission
from qsdc.common.coding.universal_hash import UniversalHash
from qsdc.common.random import RandomSource, derive_seed, make_random_source
from qsdc.protocols.cao.config import SimulatorConfig
from qsdc.protocols.cao.constants import EPR_BOUND
from qsdc.protocols.cao.simulator import postprocessing
from qsdc.protocols.cao.simulator.backends import Backend, make_backend
from qsdc.protocols.cao.simulator.mapping import (
    Box,
    interval_code,
    map_box,
    restore_block,
    restore_message,
    uniformize_block,
    uniformize_message,
)
from qsdc.protocols.cao.simulator.postprocessing import Estimate


@dataclass(frozen=True)
class Block(transmission.Block):
    uniformized: str | None = None
    payload: str | None = None


def encode_blocks(payload: str, block_bits: int) -> list[Block]:
    padded = payload.ljust(-(-len(payload) // block_bits) * block_bits, "0")
    uniformized = uniformize_message(padded)
    blocks = []
    for i in range(0, len(payload), block_bits):
        message_part = uniformized[2 * i : 2 * (i + block_bits)]
        blocks.append(Block(i, payload[i : i + block_bits], uniformized=message_part))
    return blocks


def amplify_blocks(
    payload: str, amplifier: UniversalHash, rng: RandomSource
) -> list[Block]:
    # The payload is a random input whose hash is the message, so the public
    # bits hide the message while they are fewer than the random bits.
    block_bits = amplifier.output_bits
    blocks = []
    for i in range(0, len(payload), block_bits):
        bits = payload[i : i + block_bits]
        randomness = "".join(rng.choice("01") for _ in range(amplifier.free_bits))
        hashed = amplifier.preimage(bits.ljust(block_bits, "0"), randomness)
        blocks.append(Block(i, bits, payload=hashed))
    return blocks


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
class Positions:
    # Where the pairs of a block go: the two checks and the boxes.
    count: int
    channel: list[int]
    authentication: list[int]
    signal: list[int]


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
    def __init__(self, config: SimulatorConfig, backend: Backend | None = None):
        self.config = config
        self.backend = backend or make_backend(config)
        self.code = interval_code(config)
        # Bob calibrates the checks to the honest channel he expects.
        sigma = self.backend.check_sigma()
        self.expected_failure_rate = exp(-EPR_BOUND / (2 * sigma**2))
        rate = self.expected_failure_rate
        margin = sqrt(rate * (1 - rate) / config.check_pairs)
        self.check_threshold = rate + config.check_tolerance_sigmas * margin
        self.reconciliation = None
        self.amplifier = None
        if config.reconciliation is not None:
            self.reconciliation = postprocessing.reconciliation_code(config)
            self.amplifier = UniversalHash(
                config.payload_bits,
                config.block_bits,
                seed=derive_seed(config.seed, "universal hash"),
            )

    def transmit(self, payload: str) -> Transmission:
        config = self.config
        return transmission.send_blocks(
            self.split(payload),
            config.seed,
            config.max_attempts,
            self.send_block,
        )

    def split(self, payload: str) -> list[Block]:
        # With privacy amplification, each block becomes a random payload whose
        # hash is the message. Without it, the message is uniformized.
        config = self.config
        if self.amplifier is None:
            return encode_blocks(payload, config.block_bits)
        seed = derive_seed(config.seed, "privacy amplification")
        rng = make_random_source(config.random_source, seed)
        return amplify_blocks(payload, self.amplifier, rng)

    def send_block(self, block: Block, seed: int) -> tuple[BlockRun, str | None]:
        rng = make_random_source(self.config.random_source, seed)
        self.backend.begin_run(seed)

        # 1. Preparation: Alice prepares the EPR pairs, keeps S1 and sends S2.
        positions = self.prepare_pairs(rng)

        # 2. Channel detection: both heterodyne a random group of pairs.
        channel = self.run_checks(positions.channel)
        if not channel.accepted:
            return BlockRun(positions.count, channel, None), None

        # 3. Authentication: the same check on another group, published by Bob.
        authentication = self.run_checks(positions.authentication)
        if not authentication.accepted:
            return BlockRun(positions.count, channel, authentication), None

        # 4. Gaussian mapping: Alice maps the block onto boxes and draws G1'.
        boxes = self.map_boxes(block, rng)
        g1 = [self.code.sample(box.bits, rng) for box in boxes]

        # 5. Gaussian modulation: Alice displaces S1 by G1' in x and G2 in p.
        displacements = self.modulate(g1, rng)

        # 6. Measurement: Bob measures S_info jointly with S2.
        measured = self.measure(displacements)

        # 7a. Parameter estimation: Alice reveals G2, and Bob fits his gain.
        channel_estimate = self.estimate_channel(displacements, measured)
        signals = self.decode(
            positions.signal, boxes, displacements, measured, channel_estimate
        )
        run = BlockRun(
            positions.count, channel, authentication, signals, channel_estimate
        )

        if self.reconciliation is None:
            # 7b. Without reconciliation, Bob keeps the block only if every
            # detection and parity bit matches.
            message = self.restore(signals)
        else:
            # 7b. Reconciliation: Alice's syndrome corrects Bob's payload.
            run = self.reconcile(run, boxes)
            # 7c. Privacy amplification: the hash of the payload is the message.
            message = self.amplify(run.reconciled)
        if message is None:
            return run, None
        return run, message[: len(block.bits)]

    def prepare_pairs(self, rng: RandomSource) -> Positions:
        # Each pair goes at random to one of the two checks or to a box.
        checks = self.config.check_pairs
        count = 2 * checks + self.config.boxes
        shuffled = rng.shuffled(range(count))
        return Positions(
            count,
            channel=sorted(shuffled[:checks]),
            authentication=sorted(shuffled[checks : 2 * checks]),
            signal=sorted(shuffled[2 * checks :]),
        )

    def run_checks(self, positions: list[int]) -> Stage:
        checks = []
        for index in positions:
            alice, bob = self.backend.measure_check()
            checks.append(Check(index, alice, bob))
        return Stage(tuple(checks), self.expected_failure_rate, self.check_threshold)

    def map_boxes(self, block: Block, rng: RandomSource) -> list[Box]:
        config = self.config
        if block.payload is not None:
            bits = block.payload
        else:
            bits = uniformize_block(block.uniformized, rng)
        width = config.box_bits
        boxes = []
        for i in range(0, len(bits), width):
            boxes.append(map_box(bits[i : i + width], config.detection_bits, rng))
        return boxes

    def modulate(self, g1: list[float], rng: RandomSource) -> list[complex]:
        sigma = sqrt(self.config.modulation_variance_snu)
        g2 = [rng.gauss(sigma) for _ in g1]
        displacements = []
        for x, p in zip(g1, g2):
            displacements.append(complex(x, p))
        return displacements

    def measure(self, displacements: list[complex]) -> list[complex]:
        measured = []
        for displacement in displacements:
            measured.append(self.backend.measure_signal(displacement))
        return measured

    def estimate_channel(
        self, displacements: list[complex], measured: list[complex]
    ) -> Estimate:
        # P_m carries only G2, so Bob fits P_m = gain * G2 + noise.
        g2 = [displacement.imag for displacement in displacements]
        p = [value.imag for value in measured]
        return postprocessing.estimate(g2, p)

    def decode(
        self,
        positions: list[int],
        boxes: list[Box],
        displacements: list[complex],
        measured: list[complex],
        channel_estimate: Estimate,
    ) -> tuple[Signal, ...]:
        # Bob divides X_m by his gain and reads the interval it falls in.
        signals = []
        for i, box in enumerate(boxes):
            value = measured[i].real / channel_estimate.gain
            signals.append(
                Signal(
                    index=positions[i],
                    box=box,
                    g1=displacements[i].real,
                    g2=displacements[i].imag,
                    measured=measured[i],
                    decoded_value=value,
                    decoded_bits=self.code.decode(value),
                )
            )
        return tuple(signals)

    def restore(self, signals: tuple[Signal, ...]) -> str | None:
        if not all(signal.valid for signal in signals):
            return None
        payload = "".join(signal.decoded_payload for signal in signals)
        return restore_message(restore_block(payload))

    def reconcile(self, run: BlockRun, boxes: list[Box]) -> BlockRun:
        values = [signal.decoded_value for signal in run.signals]
        bit_confidences = postprocessing.confidences(
            boxes, values, self.code, run.estimate
        )
        syndrome, reconciled = postprocessing.reconcile(
            self.reconciliation,
            boxes,
            bit_confidences,
            self.config.reconciliation.max_iterations,
        )
        return replace(run, syndrome=syndrome, reconciled=reconciled)

    def amplify(self, reconciled: str | None) -> str | None:
        if reconciled is None:
            return None
        return self.amplifier.hash(reconciled)
