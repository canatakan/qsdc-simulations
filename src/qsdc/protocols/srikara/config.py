from __future__ import annotations

from math import exp
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from qsdc.common.random import RandomSource


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


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


class Channel(Config):
    transmittance: float = 1.0
    nbar: float = 0.0


class Memory(Config):
    seconds: float = 0.0
    lifetime_seconds: float = 1.0
    efficiency: float = 1.0
    nbar: float = 0.0

    @property
    def transmittance(self) -> float:
        return self.efficiency * exp(-self.seconds / self.lifetime_seconds)


class Detector(Config):
    efficiency: float = 1.0
    electronic_variance: float = 0.0


class NoiseConfig(Config):
    forward: Channel = Channel()
    memory: Memory = Memory()
    backward: Channel = Channel()
    alice_detector: Detector = Detector()
    bob_detector: Detector = Detector()


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
