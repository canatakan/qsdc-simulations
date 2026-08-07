"""Backend contract for the CV QSDC srikara.simulator."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class MeasurementExpectation:
    """Expected mean and standard deviation for one measurement."""

    mean: float
    sigma: float


class QSDCBackend(ABC):
    """Minimal backend contract needed by the QSDC protocol."""

    name: str
    measurement_noise_sigma: float

    @abstractmethod
    def begin_run(self, seed: int) -> None:
        """Reset backend-level randomness for one protocol run."""

    @abstractmethod
    def control_measurement(
        self, alpha: complex, squeeze_r: float, theta: float, axis: str
    ) -> float:
        """Measure one control quadrature after Alice applies S(-s)."""

    @abstractmethod
    def returned_measurement(
        self, alpha: complex, squeeze_r: float, theta: float, beta: complex, axis: str
    ) -> float:
        """Measure one returned quadrature after Bob applies S(-s)."""

    @abstractmethod
    def message_response_factor(
        self, squeeze_r: float, theta: float, axis: str
    ) -> float:
        """Return the measured response to a unit message displacement."""

    def control_expectation(
        self,
        alpha: complex,
        squeeze_r: float,
        theta: float,
        axis: str,
    ) -> MeasurementExpectation:
        """Return the expectation for an Alice control measurement."""

        return MeasurementExpectation(
            mean=_component(alpha, axis),
            sigma=self.measurement_noise_sigma,
        )

    def returned_expectation(
        self,
        alpha: complex,
        squeeze_r: float,
        theta: float,
        axis: str,
    ) -> MeasurementExpectation:
        """Return the expectation for a returned mode without a message."""

        return MeasurementExpectation(
            mean=_component(alpha, axis),
            sigma=self.measurement_noise_sigma,
        )


def _component(value: complex, axis: str) -> float:
    if axis == "q":
        return value.real
    if axis == "p":
        return value.imag
    raise ValueError(f"unknown quadrature axis {axis!r}")
