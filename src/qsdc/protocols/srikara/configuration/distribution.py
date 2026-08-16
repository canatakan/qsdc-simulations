from __future__ import annotations

from abc import ABC, abstractmethod
from math import pi
from typing import Annotated, Literal, Union

from pydantic import Field, FiniteFloat, model_validator

from qsdc.common.random.base import RandomSource
from qsdc.protocols.srikara.configuration.common import (
    ConfigModel,
    NonNegativeFloat,
)


class Distribution(ConfigModel, ABC):
    @abstractmethod
    def sample(self, random_source: RandomSource) -> Union[complex, float]:
        """Sample a value using the supplied random source."""

    @abstractmethod
    def summary(self) -> str:
        """Return a compact human-readable description."""


class AlphaConfig(Distribution):
    kind: Literal["uniform_square"] = "uniform_square"
    bound: NonNegativeFloat = 2.0

    def sample(self, random_source: RandomSource) -> complex:
        return complex(
            random_source.uniform(-self.bound, self.bound),
            random_source.uniform(-self.bound, self.bound),
        )

    def summary(self) -> str:
        return f"alpha=uniform_square[bound={self.bound:g}]"


class UniformSqueezeConfig(Distribution):
    kind: Literal["uniform"] = "uniform"
    lower: NonNegativeFloat = 0.115
    upper: NonNegativeFloat = 0.576

    @model_validator(mode="after")
    def validate_bounds(self) -> UniformSqueezeConfig:
        if self.upper < self.lower:
            raise ValueError(
                "squeeze upper bound must be greater than or equal to lower"
            )
        return self

    def sample(self, random_source: RandomSource) -> float:
        return random_source.uniform(self.lower, self.upper)

    def summary(self) -> str:
        return f"r=uniform[{self.lower:g},{self.upper:g}]"


class FixedSqueezeConfig(Distribution):
    kind: Literal["fixed"] = "fixed"
    value: NonNegativeFloat

    def sample(self, random_source: RandomSource) -> float:
        return self.value

    def summary(self) -> str:
        return f"r=fixed[{self.value:g}]"


SqueezeConfig = Annotated[
    Union[UniformSqueezeConfig, FixedSqueezeConfig],
    Field(discriminator="kind"),
]


class UniformThetaConfig(Distribution):
    kind: Literal["uniform"] = "uniform"
    lower_pi: FiniteFloat = 0.0
    upper_pi: FiniteFloat = 2.0

    @model_validator(mode="after")
    def validate_bounds(self) -> UniformThetaConfig:
        if self.upper_pi < self.lower_pi:
            raise ValueError(
                "theta upper bound must be greater than or equal to lower"
            )
        return self

    def sample(self, random_source: RandomSource) -> float:
        return random_source.uniform(self.lower_pi, self.upper_pi) * pi

    def summary(self) -> str:
        lower = "0" if self.lower_pi == 0.0 else f"{self.lower_pi:g}pi"
        upper = "0" if self.upper_pi == 0.0 else f"{self.upper_pi:g}pi"
        return f"theta=uniform[{lower},{upper}]"


class FixedThetaConfig(Distribution):
    kind: Literal["fixed"] = "fixed"
    value_pi: FiniteFloat

    def sample(self, random_source: RandomSource) -> float:
        return self.value_pi * pi

    def summary(self) -> str:
        return f"theta=fixed[{self.value_pi:g}pi]"


ThetaConfig = Annotated[
    Union[UniformThetaConfig, FixedThetaConfig],
    Field(discriminator="kind"),
]
