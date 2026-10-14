from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from qsdc.common.coding.intervals import GaussianIntervalCode
from qsdc.common.coding.ldpc import LdpcCode
from qsdc.common.coding.universal_hash import UniversalHash
from qsdc.common.random import derive_seed

from ..config import SimulatorConfig
from .mapping import Box


@dataclass(frozen=True)
class Estimate:
    gain: float
    noise_variance: float

    @classmethod
    def fit(cls, g2: Sequence[float], measured_p: Sequence[float]) -> Estimate:
        # Least squares for measured_p = gain * g2 + noise.
        g2 = np.array(g2)
        measured_p = np.array(measured_p)
        power = np.dot(g2, g2)
        gain = np.dot(g2, measured_p) / power if power else 0.0

        residual = measured_p - gain * g2
        noise_variance = max(float(np.mean(residual**2)), 1e-12)

        return cls(float(gain), noise_variance)


class Postprocessor:
    def __init__(self, config: SimulatorConfig, code: GaussianIntervalCode):
        self.config = config
        self.code = code
        self.ldpc = None
        self.amplifier = None
        if config.reconciliation is not None:
            self.ldpc = reconciliation_code(config)
            self.amplifier = UniversalHash(
                config.payload_bits,
                config.block_bits,
                seed=derive_seed(config.seed, "universal hash"),
            )

    def correct(
        self, boxes: Sequence[Box], values: Sequence[float], estimate: Estimate
    ) -> tuple[str, str | None]:
        # Alice's syndrome corrects Bob's payload.
        bit_confidences = confidences(boxes, values, self.code, estimate)
        iterations = self.config.reconciliation.max_iterations

        return reconcile(self.ldpc, boxes, bit_confidences, iterations)

    def amplify(self, reconciled: str | None) -> str | None:
        # The hash of the payload is the message.
        if reconciled is None:
            return None

        return self.amplifier.hash(reconciled)


def reconciliation_code(config: SimulatorConfig) -> LdpcCode:
    settings = config.reconciliation
    length = config.payload_bits
    code = LdpcCode.regular(
        length,
        checks=config.syndrome_bits,
        column_weight=settings.column_weight,
        seed=config.seed,
    )

    # One more check per box: the parity of its payload bits, which Bob knows
    # from the announced parity and detection bits.
    box_rows = []
    for start in range(0, length, config.box_bits):
        box_rows.append(range(start, start + config.box_bits))

    return code.extended(box_rows)


def confidences(
    boxes: Sequence[Box],
    values: Sequence[float],
    code: GaussianIntervalCode,
    estimate: Estimate,
) -> list[float]:
    noise_variance = estimate.noise_variance / estimate.gain**2

    result = []
    for box, value in zip(boxes, values):
        # Only the labels that carry the announced detection bits are possible.
        probabilities = code.probabilities(value, noise_variance)
        possible = {
            label: probability
            for label, probability in probabilities.items()
            if box.detection_matches(label)
        }

        for position in box.payload_positions:
            zero = sum(p for label, p in possible.items() if label[position] == "0")
            one = sum(p for label, p in possible.items() if label[position] == "1")
            result.append(LdpcCode.log_ratio(zero, one))

    return result


def reconcile(
    code: LdpcCode,
    boxes: Sequence[Box],
    confidences: Sequence[float],
    max_iterations: int,
) -> tuple[str, str | None]:
    alice_payload = "".join(box.payload for box in boxes)
    ldpc_checks = code.checks - len(boxes)
    syndrome = code.syndrome(alice_payload)[:ldpc_checks]

    # Bob decodes with the syndrome and the payload parity of each box.
    announced = "".join(box.payload_parity for box in boxes)
    reconciled = code.decode(confidences, syndrome + announced, max_iterations)

    return syndrome, reconciled
