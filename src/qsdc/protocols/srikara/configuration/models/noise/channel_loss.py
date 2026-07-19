"""Configuration models for optical channel loss."""

from typing import Annotated, Literal, Union

from pydantic import Field

from qsdc.protocols.srikara.configuration.models.base import (
    ConfigurationModel,
    NonNegativeFloat,
    Probability,
)
from qsdc.protocols.srikara.simulator.noise import PureLoss, ThermalLoss


class PureLossConfig(ConfigurationModel):
    type: Literal["loss"] = "loss"
    transmittance: Probability

    def build(self) -> PureLoss:
        return PureLoss(transmittance=self.transmittance)


class ThermalLossConfig(ConfigurationModel):
    type: Literal["thermal_loss"] = "thermal_loss"
    transmittance: Probability
    environment_nbar: NonNegativeFloat

    def build(self) -> ThermalLoss:
        return ThermalLoss(
            transmittance=self.transmittance,
            environment_nbar=self.environment_nbar,
        )


ChannelEffectConfig = Annotated[
    Union[PureLossConfig, ThermalLossConfig],
    Field(discriminator="type"),
]
