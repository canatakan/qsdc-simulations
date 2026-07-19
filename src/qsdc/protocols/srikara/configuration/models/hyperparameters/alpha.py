"""Configuration models for alpha distributions."""

from __future__ import annotations

from typing import Literal

from qsdc.protocols.srikara.configuration.models.base import (
    ConfigurationModel,
    NonNegativeFloat,
)
from qsdc.protocols.srikara.simulator.distributions import UniformSquareAlpha


class UniformSquareAlphaConfig(ConfigurationModel):
    kind: Literal["uniform_square"] = "uniform_square"
    bound: NonNegativeFloat = 2.0

    def build(self) -> UniformSquareAlpha:
        return UniformSquareAlpha(bound=self.bound)

    @classmethod
    def from_runtime(
        cls,
        distribution: UniformSquareAlpha,
    ) -> "UniformSquareAlphaConfig":
        return cls(bound=distribution.bound)
