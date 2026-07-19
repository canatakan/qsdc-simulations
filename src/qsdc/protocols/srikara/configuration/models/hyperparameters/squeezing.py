"""Configuration models for squeezing distributions."""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import Field

from qsdc.protocols.srikara.configuration.models.base import (
    ConfigurationModel,
    NonNegativeFloat,
)
from qsdc.protocols.srikara.simulator.distributions import (
    FixedSqueezeR,
    UniformSqueezeR,
)


class BaseSqueezeConfigModel(ConfigurationModel):
    @classmethod
    def from_runtime(
        cls,
        distribution: UniformSqueezeR | FixedSqueezeR,
    ) -> "BaseSqueezeConfigModel":
        if isinstance(distribution, UniformSqueezeR):
            return UniformSqueezeConfig(
                lower=distribution.lower,
                upper=distribution.upper,
            )
        if isinstance(distribution, FixedSqueezeR):
            return FixedSqueezeConfig(value=distribution.value)
        raise TypeError(
            "cannot serialize squeeze distribution "
            f"{type(distribution).__name__!r}"
        )


class UniformSqueezeConfig(BaseSqueezeConfigModel):
    kind: Literal["uniform"] = "uniform"
    lower: NonNegativeFloat
    upper: NonNegativeFloat

    def build(self) -> UniformSqueezeR:
        return UniformSqueezeR(lower=self.lower, upper=self.upper)


class FixedSqueezeConfig(BaseSqueezeConfigModel):
    kind: Literal["fixed"] = "fixed"
    value: NonNegativeFloat

    def build(self) -> FixedSqueezeR:
        return FixedSqueezeR(value=self.value)


SqueezeConfig = Annotated[
    Union[UniformSqueezeConfig, FixedSqueezeConfig],
    Field(discriminator="kind"),
]
