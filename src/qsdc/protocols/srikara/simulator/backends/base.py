"""Backend contract for the CV QSDC srikara.simulator."""

from __future__ import annotations

from abc import ABC, abstractmethod


class QSDCBackend(ABC):
    """Minimal backend contract needed by the QSDC protocol."""

    name: str
    default_tolerance_sigmas: float
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
