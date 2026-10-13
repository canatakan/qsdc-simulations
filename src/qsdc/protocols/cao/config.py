from __future__ import annotations

from math import acosh
from typing import Literal, Optional

from pydantic import model_validator

from qsdc.common.config.base import (
    Config,
    Fraction,
    NonNegative,
    NonNegativeInt,
    Positive,
    PositiveInt,
)
from qsdc.common.config.noise import BASELINES, Channel, Detector, Environment, Memory


class NoiseConfig(Config):
    alice_memory: Memory = Memory()
    channel: Channel = Channel()
    bob_memory: Memory = Memory()
    alice_detector: Detector = Detector()
    bob_detector: Detector = Detector()

    @classmethod
    def from_environment(cls, environment: Environment) -> NoiseConfig:
        return cls(
            alice_memory=environment.memory,
            channel=environment.fibre,
            bob_memory=environment.memory,
            alice_detector=environment.detector,
            bob_detector=environment.detector,
        )


NOISES = {
    name: NoiseConfig.from_environment(environment)
    for name, environment in BASELINES.items()
}

# The smallest syndrome fraction that reconciled 12 of 12 blocks on each noise
# baseline. The longer links have none: no fraction leaves message bits.
SYNDROME_FRACTIONS = {"clean": 0.10, "lab": 0.25, "metro_5km": 0.40}


class Reconciliation(Config):
    syndrome_fraction: Fraction = 0.3
    column_weight: PositiveInt = 3
    max_iterations: PositiveInt = 100
    secrecy_margin: NonNegativeInt = 32


class SimulatorConfig(Config):
    backend: Literal["analytic", "sf", "sf-sampled"] = "sf-sampled"
    random_source: Literal["classical", "sf-bs-qrng"] = "classical"
    seed: int = 11

    noise: NoiseConfig = NoiseConfig()

    squeeze_r: NonNegative = acosh(9.0) / 2
    modulation_variance_snu: Positive = 8.0

    boxes: PositiveInt = 512
    box_bits: PositiveInt = 2
    detection_bits: PositiveInt = 1

    check_pairs: PositiveInt = 64
    check_tolerance_sigmas: Positive = 3.0

    reconciliation: Optional[Reconciliation] = Reconciliation()  # noqa: UP045
    max_attempts: PositiveInt = 1

    @property
    def payload_bits(self) -> int:
        return self.boxes * self.box_bits

    @property
    def syndrome_bits(self) -> int:
        if self.reconciliation is None:
            return 0

        return round(self.reconciliation.syndrome_fraction * self.payload_bits)

    @property
    def public_bits(self) -> int:
        # What Eve can read about the payload on the classical channel: one
        # announced parity bit per box and the reconciliation syndrome.
        return self.boxes + self.syndrome_bits

    @property
    def block_bits(self) -> int:
        if self.reconciliation is None:
            # Both uniformizations double the bits.
            return self.payload_bits // 4

        margin = self.reconciliation.secrecy_margin
        return self.payload_bits - self.public_bits - margin

    @model_validator(mode="after")
    def _message_fits(self) -> SimulatorConfig:
        if self.reconciliation is None and self.payload_bits % 4:
            raise ValueError("the payload bits must be divisible by 4")

        if self.reconciliation is not None and self.syndrome_bits < 1:
            raise ValueError("the syndrome fraction leaves no syndrome bits")

        if self.block_bits < 1:
            raise ValueError(
                "no secure message bits are left: the announced parities, the "
                "syndrome and the secrecy margin cover all payload bits"
            )

        return self
