from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import Field

from qsdc.common.config import Config
from qsdc.common.noise import Channel, Detector, Environment, Memory
from qsdc.common.random import RandomSource


class Fixed(Config):
    kind: Literal["fixed"] = "fixed"
    value: float

    def sample(self, rng: RandomSource) -> float:
        return self.value

    def __str__(self) -> str:
        return f"{self.value:g}"


class Uniform(Config):
    kind: Literal["uniform"] = "uniform"
    lower: float
    upper: float

    def sample(self, rng: RandomSource) -> float:
        return rng.uniform(self.lower, self.upper)

    def __str__(self) -> str:
        return f"U[{self.lower:g}, {self.upper:g}]"


Distribution = Annotated[Union[Fixed, Uniform], Field(discriminator="kind")]


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


class SimulatorConfig(Config):
    backend: Literal["analytic", "sf", "sf-sampled"] = "analytic"
    random_source: Literal["classical", "sf-bs-qrng"] = "classical"
    seed: int = 11
    noise: NoiseConfig = NoiseConfig()
    alpha_variance_snu: float = 64 / 3
    squeeze_r: Distribution = Uniform(lower=0.115, upper=0.576)
    theta_pi: Distribution = Uniform(lower=0.0, upper=2.0)
    tolerance_sigmas: float = 1.0
    intervals: Literal[
        "default",
        "gray",
        "gaussian_gray",
    ] = "default"
    axis_policy: Literal["random", "best_qp", "aligned"] = "random"
    error_correction: Literal["none", "parity", "secded"] = "none"
    max_attempts: int = 1
