"""Configuration models for theta distributions."""

from __future__ import annotations

from math import pi
from typing import Annotated, Literal, Union

from pydantic import Field

from qsdc.protocols.srikara.configuration.models.base import ConfigurationModel
from qsdc.protocols.srikara.simulator.distributions import FixedTheta, UniformTheta


class BaseThetaConfigModel(ConfigurationModel):
    @classmethod
    def from_runtime(
        cls,
        distribution: UniformTheta | FixedTheta,
    ) -> "BaseThetaConfigModel":
        if isinstance(distribution, UniformTheta):
            return UniformThetaConfig(
                lower_pi=distribution.lower / pi,
                upper_pi=distribution.upper / pi,
            )
        if isinstance(distribution, FixedTheta):
            return FixedThetaConfig(value_pi=distribution.value / pi)
        raise TypeError(
            "cannot serialize theta distribution "
            f"{type(distribution).__name__!r}"
        )


class UniformThetaConfig(BaseThetaConfigModel):
    kind: Literal["uniform"] = "uniform"
    lower_pi: float = 0.0
    upper_pi: float = 2.0

    def build(self) -> UniformTheta:
        return UniformTheta(lower=self.lower_pi * pi, upper=self.upper_pi * pi)


class FixedThetaConfig(BaseThetaConfigModel):
    kind: Literal["fixed"] = "fixed"
    value_pi: float

    def build(self) -> FixedTheta:
        return FixedTheta(value=self.value_pi * pi)


ThetaConfig = Annotated[
    Union[UniformThetaConfig, FixedThetaConfig],
    Field(discriminator="kind"),
]
