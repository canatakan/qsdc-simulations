"""SF backend that reads ideal Gaussian state means."""

from __future__ import annotations

from dataclasses import dataclass

from srikara.simulator.core.config import DEFAULT_EXACT_TOLERANCE
from srikara.simulator.backends.base import QSDCBackend
from srikara.simulator.backends.sf.calculations import (
    build_control_program,
    build_returned_program,
    mean_component,
    message_unit_beta,
)


@dataclass(frozen=True)
class SFBackend(QSDCBackend):
    """SF Gaussian circuits with exact state-mean readout."""

    name: str = "sf"
    default_tolerance: float = DEFAULT_EXACT_TOLERANCE

    def begin_run(self, seed: int) -> None:
        pass

    def control_measurement(
        self, alpha: complex, squeeze_r: float, theta: float, axis: str
    ) -> float:
        return mean_component(build_control_program(alpha, squeeze_r, theta), axis)

    def returned_measurement(
        self, alpha: complex, squeeze_r: float, theta: float, beta: complex, axis: str
    ) -> float:
        return mean_component(
            build_returned_program(alpha, squeeze_r, theta, beta), axis
        )

    def message_response_factor(
        self, squeeze_r: float, theta: float, axis: str
    ) -> float:
        return mean_component(
            build_returned_program(
                alpha=0j,
                squeeze_r=squeeze_r,
                theta=theta,
                beta=message_unit_beta(),
            ),
            axis,
        )
