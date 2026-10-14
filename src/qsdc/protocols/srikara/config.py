from __future__ import annotations

from pathlib import Path
from typing import Literal

from qsdc.common.config.base import (
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


class SimulatorConfig(Config):
    backend: Literal["analytic", "sf", "sf-sampled"] = "analytic"
    random_source: Literal["classical", "sf-bs-qrng"] = "classical"
    seed: int = 11

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

    error_correction: Literal["none", "parity", "secded"] = "none"
    max_attempts: PositiveInt = 1


PRESETS = load_presets(Path(__file__).with_name("presets.yaml"), SimulatorConfig)
