"""Analytic Cao-protocol backend."""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, sqrt

from qsdc.protocols.cao.simulator.backends.base import (
    CorrelatedBeams,
    CorrelationNoise,
    GaussianMappingBackend,
    JointMeasurement,
    ModulatedBeam,
    VacuumQuadratures,
)


@dataclass(frozen=True)
class AnalyticBackend(GaussianMappingBackend):
    name: str = "analytic"

    def prepare_correlated_beams(
        self,
        squeeze_r: float,
        vacuum: VacuumQuadratures,
    ) -> CorrelatedBeams:
        squeezed_x1 = exp(-squeeze_r) * vacuum.x1
        squeezed_p1 = exp(squeeze_r) * vacuum.p1
        squeezed_x2 = exp(squeeze_r) * vacuum.x2
        squeezed_p2 = exp(-squeeze_r) * vacuum.p2

        return CorrelatedBeams(
            signal_x=(squeezed_x1 + squeezed_x2) / sqrt(2.0),
            signal_p=(squeezed_p1 + squeezed_p2) / sqrt(2.0),
            detection_x=(squeezed_x2 - squeezed_x1) / sqrt(2.0),
            detection_p=(squeezed_p2 - squeezed_p1) / sqrt(2.0),
        )

    def correlation_noise(self, beams: CorrelatedBeams) -> CorrelationNoise:
        return CorrelationNoise(
            delta_x=(beams.signal_x - beams.detection_x) / sqrt(2.0),
            delta_p=(beams.signal_p + beams.detection_p) / sqrt(2.0),
        )

    def modulate(
        self,
        beams: CorrelatedBeams,
        x_value: float,
        p_value: float,
    ) -> ModulatedBeam:
        return ModulatedBeam(
            info_x=beams.signal_x + sqrt(2.0) * x_value,
            info_p=beams.signal_p + sqrt(2.0) * p_value,
            detection_x=beams.detection_x,
            detection_p=beams.detection_p,
            x_modulation=x_value,
            p_modulation=p_value,
        )

    def measure_message(self, beam: ModulatedBeam) -> JointMeasurement:
        return JointMeasurement(
            x_message=(beam.info_x - beam.detection_x) / sqrt(2.0),
            p_message=(beam.info_p + beam.detection_p) / sqrt(2.0),
        )
