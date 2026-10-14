from __future__ import annotations

from dataclasses import dataclass

from qsdc.common.coding.intervals import GaussianIntervalCode

from .backends import Backend
from .mapping import Box
from .postprocessing import Estimate


@dataclass(frozen=True)
class Signal:
    index: int
    box: Box
    g1: float
    g2: float
    measured: complex
    decoded_value: float
    decoded_bits: str

    @property
    def correct(self) -> bool:
        return self.decoded_bits == self.box.bits

    @property
    def detection_valid(self) -> bool:
        return self.box.detection_matches(self.decoded_bits)

    @property
    def parity_valid(self) -> bool:
        return self.box.parity_matches(self.decoded_bits)

    @property
    def valid(self) -> bool:
        return self.detection_valid and self.parity_valid

    @property
    def decoded_payload(self) -> str:
        return self.box.unmap(self.decoded_bits)


class Receiver:
    def __init__(self, backend: Backend, code: GaussianIntervalCode):
        self.backend = backend
        self.code = code

    def measure(self, displacements: list[complex]) -> list[complex]:
        measured = []
        for displacement in displacements:
            measured.append(self.backend.measure_signal(displacement))

        return measured

    def estimate(
        self, displacements: list[complex], measured: list[complex]
    ) -> Estimate:
        # P_m carries only G2, so Bob fits P_m = gain * G2 + noise.
        g2 = [displacement.imag for displacement in displacements]
        p = [value.imag for value in measured]

        return Estimate.fit(g2, p)

    def decode(
        self,
        positions: list[int],
        boxes: list[Box],
        displacements: list[complex],
        measured: list[complex],
        estimate: Estimate,
    ) -> tuple[Signal, ...]:
        # Bob divides X_m by his gain and reads the interval it falls in.
        signals = []
        for i, box in enumerate(boxes):
            value = measured[i].real / estimate.gain
            signals.append(
                Signal(
                    index=positions[i],
                    box=box,
                    g1=displacements[i].real,
                    g2=displacements[i].imag,
                    measured=measured[i],
                    decoded_value=value,
                    decoded_bits=self.code.decode(value),
                )
            )

        return tuple(signals)
