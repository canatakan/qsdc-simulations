"""Configuration model for detector inefficiency."""

from typing import Literal

from qsdc.protocols.srikara.configuration.models.base import (
    ConfigurationModel,
    Probability,
)
from qsdc.protocols.srikara.simulator.noise import DetectorInefficiency


class DetectorInefficiencyConfig(ConfigurationModel):
    type: Literal["detector_inefficiency"] = "detector_inefficiency"
    efficiency: Probability

    def build(self) -> DetectorInefficiency:
        return DetectorInefficiency(efficiency=self.efficiency)
