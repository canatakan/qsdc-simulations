"""Strawberry Fields operations for validated noise configurations."""

from __future__ import annotations

from math import sqrt

import numpy as np
from strawberryfields import hbar, ops

from qsdc.protocols.srikara.configuration.noise import (
    ChannelEffectConfig,
    DetectorInefficiencyConfig,
    ElectronicNoiseConfig,
    PureLossConfig,
)


class Noise:
    """Apply configured noise to Strawberry Fields registers and measurements."""

    @staticmethod
    def apply_channel_noise(
        register: object,
        effects: list[ChannelEffectConfig],
    ) -> None:
        for effect in effects:
            if isinstance(effect, PureLossConfig):
                ops.LossChannel(effect.transmittance) | register
            else:
                ops.ThermalLossChannel(
                    effect.transmittance,
                    effect.environment_nbar,
                ) | register

    @staticmethod
    def apply_detector_noise(
        register: object,
        effects: list[DetectorInefficiencyConfig],
    ) -> None:
        for effect in effects:
            ops.LossChannel(effect.efficiency) | register

    @staticmethod
    def apply_electronic_noise(
        measured: float,
        effects: list[ElectronicNoiseConfig],
    ) -> float:
        for effect in effects:
            variance = Noise.readout_variance(effect.variance_snu)
            if variance != 0.0:
                measured += float(np.random.normal(0.0, sqrt(variance)))
        return measured

    @staticmethod
    def readout_variance(variance_snu: float) -> float:
        sf_vacuum_variance = hbar / 2.0
        normalize_quadrature_scale = sqrt(2.0 * hbar)
        vacuum_component_variance = (
            sf_vacuum_variance / normalize_quadrature_scale ** 2
        )
        return variance_snu * vacuum_component_variance
