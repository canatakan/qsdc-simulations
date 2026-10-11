from __future__ import annotations

from math import acosh, exp
from typing import Literal

from pydantic import model_validator

from qsdc.common.config import Config


class SimulatorConfig(Config):
    random_source: Literal["classical", "sf-bs-qrng"] = "classical"
    seed: int = 11
    squeeze_r: float = acosh(9.0) / 2
    modulation_variance_snu: float = 8.0
    block_bits: int = 2
    boxes: int = 4
    detection_bits: int = 1
    check_pairs: int = 4
    check_failure_threshold: float = exp(-1.0)
    max_attempts: int = 1

    @property
    def box_bits(self) -> int:
        return 4 * self.block_bits // self.boxes

    @model_validator(mode="after")
    def _whole_boxes(self) -> SimulatorConfig:
        if 4 * self.block_bits % self.boxes:
            raise ValueError("4 * block_bits must be divisible by boxes")
        return self
