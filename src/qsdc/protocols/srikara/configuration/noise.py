from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import Field

from qsdc.protocols.srikara.configuration.common import (
    ConfigModel,
    NonNegativeFloat,
    Probability,
)

class PureLossConfig(ConfigModel):
    type: Literal["loss"] = "loss"
    transmittance: Probability


class ThermalLossConfig(ConfigModel):
    type: Literal["thermal_loss"] = "thermal_loss"
    transmittance: Probability
    environment_nbar: NonNegativeFloat


ChannelEffectConfig = Annotated[
    Union[PureLossConfig, ThermalLossConfig],
    Field(discriminator="type"),
]


class DetectorInefficiencyConfig(ConfigModel):
    type: Literal["detector_inefficiency"] = "detector_inefficiency"
    efficiency: Probability


class ElectronicNoiseConfig(ConfigModel):
    type: Literal["electronic_noise"] = "electronic_noise"
    variance_snu: NonNegativeFloat


class NoiseConfig(ConfigModel):
    forward: list[ChannelEffectConfig] = Field(default_factory=list)
    alice_delay: list[ChannelEffectConfig] = Field(default_factory=list)
    return_path: list[ChannelEffectConfig] = Field(default_factory=list)
    alice_detector: list[DetectorInefficiencyConfig] = Field(default_factory=list)
    alice_readout: list[ElectronicNoiseConfig] = Field(default_factory=list)
    bob_detector: list[DetectorInefficiencyConfig] = Field(default_factory=list)
    bob_readout: list[ElectronicNoiseConfig] = Field(default_factory=list)
