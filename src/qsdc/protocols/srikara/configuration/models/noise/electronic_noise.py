"""Configuration model for classical electronic readout noise."""

from typing import Literal

from qsdc.protocols.srikara.configuration.models.base import (
    ConfigurationModel,
    NonNegativeFloat,
)
from qsdc.protocols.srikara.simulator.noise import ElectronicNoise


class ElectronicNoiseConfig(ConfigurationModel):
    type: Literal["electronic_noise"] = "electronic_noise"
    variance_snu: NonNegativeFloat

    def build(self) -> ElectronicNoise:
        return ElectronicNoise(variance_snu=self.variance_snu)
