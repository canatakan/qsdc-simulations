"""Validated configuration for one complete Srikara transmission."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from qsdc.protocols.srikara.configuration.common import (
    ConfigModel,
    NonNegativeFloat,
    NonNegativeInteger,
    PositiveInteger,
)
from qsdc.protocols.srikara.configuration.distribution import (
    AlphaConfig,
    SqueezeConfig,
    ThetaConfig,
    UniformSqueezeConfig,
    UniformThetaConfig,
)
from qsdc.protocols.srikara.configuration.noise import NoiseConfig

BackendName = Literal["analytic", "sf", "sf-sampled", "sf-noise"]
RandomSourceName = Literal["classical", "sf-bs-qrng"]
IntervalPolicy = Literal[
    "default",
    "optimized_v4",
    "optimized_v8",
    "optimized_v12",
]
AxisPolicy = Literal["random", "optimized"]
ErrorCorrection = Literal["none", "secded"]


class SimulatorConfig(ConfigModel):
    """All choices needed to execute one logical payload."""

    backend: BackendName = "analytic"
    noise: NoiseConfig = Field(default_factory=NoiseConfig)
    random_source: RandomSourceName = "classical"
    alpha_distribution: AlphaConfig = Field(default_factory=AlphaConfig)
    squeeze_r_distribution: SqueezeConfig = Field(
        default_factory=UniformSqueezeConfig,
    )
    theta_distribution: ThetaConfig = Field(default_factory=UniformThetaConfig)
    tolerance_sigmas: NonNegativeFloat = 1.0
    intervals: IntervalPolicy = "default"
    check_axis_policy: AxisPolicy = "random"
    message_axis_policy: AxisPolicy = "random"
    seed: NonNegativeInteger = 11
    error_correction: ErrorCorrection = "none"
    max_attempts_per_block: PositiveInteger = 1

    @model_validator(mode="after")
    def retries_require_error_correction(self) -> SimulatorConfig:
        if self.max_attempts_per_block > 1 and self.error_correction == "none":
            raise ValueError("retries require SECDED error correction")
        return self
