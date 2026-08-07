"""Configuration model for composing effects by protocol stage."""

from __future__ import annotations

from pydantic import Field

from qsdc.protocols.srikara.configuration.models.base import ConfigurationModel
from qsdc.protocols.srikara.configuration.models.noise.channel_loss import (
    ChannelEffectConfig,
    PureLossConfig,
    ThermalLossConfig,
)
from qsdc.protocols.srikara.configuration.models.noise.detector_inefficiency import (
    DetectorInefficiencyConfig,
)
from qsdc.protocols.srikara.configuration.models.noise.electronic_noise import (
    ElectronicNoiseConfig,
)
from qsdc.protocols.srikara.simulator.noise import (
    DetectorInefficiency,
    ElectronicNoise,
    NoiseModel,
    PureLoss,
    ThermalLoss,
)


class NoiseConfig(ConfigurationModel):
    """Ordered noise effects applied at each supported protocol stage."""

    forward: list[ChannelEffectConfig] = Field(default_factory=list)
    alice_delay: list[ChannelEffectConfig] = Field(default_factory=list)
    return_path: list[ChannelEffectConfig] = Field(default_factory=list)
    alice_detector: list[DetectorInefficiencyConfig] = Field(default_factory=list)
    alice_readout: list[ElectronicNoiseConfig] = Field(default_factory=list)
    bob_detector: list[DetectorInefficiencyConfig] = Field(default_factory=list)
    bob_readout: list[ElectronicNoiseConfig] = Field(default_factory=list)

    def build(self) -> NoiseModel:
        return NoiseModel({
            stage: tuple(effect.build() for effect in effects)
            for stage, effects in self
        })

    @classmethod
    def from_runtime(cls, model: NoiseModel) -> "NoiseConfig":
        stages: dict[str, list[ConfigurationModel]] = {}
        for stage in cls.model_fields:
            effects: list[ConfigurationModel] = []
            for effect in model.at(stage):
                if isinstance(effect, PureLoss):
                    effects.append(PureLossConfig(
                        transmittance=effect.transmittance,
                    ))
                elif isinstance(effect, ThermalLoss):
                    effects.append(ThermalLossConfig(
                        transmittance=effect.transmittance,
                        environment_nbar=effect.environment_nbar,
                    ))
                elif isinstance(effect, DetectorInefficiency):
                    effects.append(DetectorInefficiencyConfig(
                        efficiency=effect.efficiency,
                    ))
                elif isinstance(effect, ElectronicNoise):
                    effects.append(ElectronicNoiseConfig(
                        variance_snu=effect.variance_snu,
                    ))
                else:
                    raise TypeError(
                        f"cannot serialize noise effect {type(effect).__name__!r}"
                    )
            stages[stage] = effects
        return cls.model_validate(stages)
