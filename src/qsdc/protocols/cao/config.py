from __future__ import annotations

from math import acosh, exp
from typing import Literal, Optional

from pydantic import model_validator

from qsdc.common.config.base import Config
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


class Reconciliation(Config):
    syndrome_fraction: float = 0.5
    column_weight: int = 3
    max_iterations: int = 100


class SimulatorConfig(Config):
    random_source: Literal["classical", "sf-bs-qrng"] = "classical"
    seed: int = 11
    noise: NoiseConfig = NoiseConfig()
    squeeze_r: float = acosh(9.0) / 2
    modulation_variance_snu: float = 8.0
    block_bits: int = 256
    boxes: int = 512
    detection_bits: int = 1
    check_pairs: int = 64
    check_failure_threshold: float = exp(-1.0)
    reconciliation: Optional[Reconciliation] = Reconciliation()  # noqa: UP045
    max_attempts: int = 1

    @property
    def payload_bits(self) -> int:
        return 4 * self.block_bits

    @property
    def box_bits(self) -> int:
        return 4 * self.block_bits // self.boxes

    @model_validator(mode="after")
    def _whole_boxes(self) -> SimulatorConfig:
        if 4 * self.block_bits % self.boxes:
            raise ValueError("4 * block_bits must be divisible by boxes")
        return self
