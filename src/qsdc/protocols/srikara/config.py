from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import model_validator

from qsdc.common.config.base import (
    BaseSimulatorConfig,
    Config,
    Distribution,
    NonNegative,
    Positive,
    PositiveInt,
    Uniform,
)
from qsdc.common.config.noise import BASELINES, Channel, Detector, Environment, Memory
from qsdc.common.config.presets import load_presets

from .constants import MESSAGE_VARIANCE_SNU


class NoiseConfig(Config):
    forward: Channel = Channel()
    memory: Memory = Memory()
    backward: Channel = Channel()
    alice_detector: Detector = Detector()
    bob_detector: Detector = Detector()

    @classmethod
    def from_environment(cls, environment: Environment) -> NoiseConfig:
        return cls(
            forward=environment.fibre,
            memory=environment.memory,
            backward=environment.fibre,
            alice_detector=environment.detector,
            bob_detector=environment.detector,
        )


NOISES = {
    name: NoiseConfig.from_environment(environment)
    for name, environment in BASELINES.items()
}


class LdpcConfig(Config):
    data_bits: PositiveInt = 96
    parity_bits: PositiveInt = 96
    column_weight: PositiveInt = 3
    max_iterations: PositiveInt = 100
    seed: int = 0

    @model_validator(mode="after")
    def _code_shape(self) -> LdpcConfig:
        if (self.data_bits + self.parity_bits) % 3:
            raise ValueError("LDPC codeword length must be divisible by 3")

        if self.column_weight > self.parity_bits:
            raise ValueError("LDPC column_weight must not exceed parity_bits")

        return self


class SimulatorConfig(BaseSimulatorConfig):
    backend: Literal["analytic", "sf", "sf-sampled"] = "analytic"

    noise: NoiseConfig = NoiseConfig()

    alpha_variance_snu: NonNegative = MESSAGE_VARIANCE_SNU
    squeeze_r: Distribution = Uniform(lower=0.115, upper=0.576)
    theta_pi: Distribution = Uniform(lower=0.0, upper=2.0)
    tolerance_sigmas: Positive = 1.0

    intervals: Literal[
        "default",
        "gray",
        "gaussian_gray",
    ] = "default"
    axis_policy: Literal["random", "best_qp", "aligned"] = "random"

    error_correction: Literal["none", "parity", "secded", "ldpc"] = "none"
    ldpc: LdpcConfig = LdpcConfig()


PRESETS = load_presets(Path(__file__).with_name("presets.yaml"), SimulatorConfig)
