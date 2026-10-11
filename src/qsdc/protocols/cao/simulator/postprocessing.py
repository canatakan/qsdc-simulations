from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import log, sqrt
from statistics import NormalDist

import numpy as np

from qsdc.common.coding.intervals import GaussianIntervalCode
from qsdc.common.coding.ldpc import MAX_CONFIDENCE, LdpcCode
from qsdc.protocols.cao.config import SimulatorConfig
from qsdc.protocols.cao.simulator.mapping import Box


@dataclass(frozen=True)
class Estimate:
    gain: float
    noise_variance: float


def estimate(g2: Sequence[float], measured_p: Sequence[float]) -> Estimate:
    g2 = np.array(g2)
    measured_p = np.array(measured_p)
    gain = np.dot(g2, measured_p) / np.dot(g2, g2)
    residual = measured_p - gain * g2
    noise_variance = max(float(np.mean(residual**2)), 1e-12)
    return Estimate(float(gain), noise_variance)


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
        probabilities = label_probabilities(value, code, noise_variance)
        possible = {
            label: probability
            for label, probability in probabilities.items()
            if matches_detection(label, box)
        }
        for position in payload_positions(box):
            zero = sum(p for label, p in possible.items() if label[position] == "0")
            one = sum(p for label, p in possible.items() if label[position] == "1")
            result.append(log_ratio(zero, one))
    return result


def label_probabilities(
    value: float, code: GaussianIntervalCode, noise_variance: float
) -> dict[str, float]:
    # G1' is Gaussian with variance V_A, and Bob reads it with Gaussian noise.
    # Given his value, G1' is Gaussian around the value pulled towards zero.
    prior_variance = code.sigma**2
    shrink = prior_variance / (prior_variance + noise_variance)
    posterior = NormalDist(value * shrink, sqrt(shrink * noise_variance))
    probabilities = {}
    for label in code.labels:
        lower, upper = code.interval(label)
        probabilities[label] = posterior.cdf(upper) - posterior.cdf(lower)
    return probabilities


def matches_detection(label: str, box: Box) -> bool:
    return all(label[i] == box.bits[i] for i in box.detection)


def payload_positions(box: Box) -> list[int]:
    return [i for i in range(len(box.bits)) if i not in box.detection]


def log_ratio(zero: float, one: float) -> float:
    if zero <= 0 and one <= 0:
        return 0.0
    if one <= 0:
        return MAX_CONFIDENCE
    if zero <= 0:
        return -MAX_CONFIDENCE
    return log(zero / one)


def reconcile(
    code: LdpcCode,
    boxes: Sequence[Box],
    confidences: Sequence[float],
    max_iterations: int,
) -> tuple[str, str | None]:
    alice_payload = "".join(box.payload for box in boxes)
    ldpc_checks = code.checks - len(boxes)
    syndrome = code.syndrome(alice_payload)[:ldpc_checks]
    announced = "".join(box.payload_parity for box in boxes)
    reconciled = code.decode(confidences, syndrome + announced, max_iterations)
    return syndrome, reconciled
