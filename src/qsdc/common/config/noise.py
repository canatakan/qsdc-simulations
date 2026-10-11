from __future__ import annotations

from math import exp
from pathlib import Path

import yaml

from qsdc.common.config.base import Config


class Channel(Config):
    transmittance: float = 1.0
    nbar: float = 0.0


class Memory(Config):
    seconds: float = 0.0
    lifetime_seconds: float = 1.0
    efficiency: float = 1.0
    nbar: float = 0.0

    @property
    def transmittance(self) -> float:
        return self.efficiency * exp(-self.seconds / self.lifetime_seconds)


class Detector(Config):
    efficiency: float = 1.0
    electronic_variance: float = 0.0


class Environment(Config):
    fibre: Channel = Channel()
    memory: Memory = Memory()
    detector: Detector = Detector()


BASELINES = {
    name: Environment.model_validate(spec)
    for name, spec in yaml.safe_load(
        (Path(__file__).parent / "noises.yaml").read_text()
    ).items()
}
