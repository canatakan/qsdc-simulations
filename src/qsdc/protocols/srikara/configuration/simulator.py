"""Validated configuration consumed directly by the Srikara simulator."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

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


class SimulatorConfig(ConfigModel):
    """Simple, serializable input for one protocol simulation."""

    n_states: PositiveInteger = 8
    alpha_distribution: AlphaConfig = Field(default_factory=AlphaConfig)
    squeeze_r_distribution: SqueezeConfig = Field(
        default_factory=UniformSqueezeConfig,
    )
    theta_distribution: ThetaConfig = Field(default_factory=UniformThetaConfig)
    tolerance_sigmas: NonNegativeFloat = 1.0
    intervals: Literal[
        "default",
        "optimized_v4",
        "optimized_v8",
        "optimized_v12",
    ] = "default"
    check_axis_policy: Literal["random", "optimized"] = "random"
    message_axis_policy: Literal["random", "optimized"] = "random"
    seed: NonNegativeInteger = 11
