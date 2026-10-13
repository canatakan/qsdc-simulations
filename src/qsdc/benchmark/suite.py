from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from qsdc.common.config.base import Config
from qsdc.common.transmission import Transmission

from .metrics import RunMetrics


class Suite(ABC):
    # One protocol's benchmark: how to run and measure its simulator, its
    # studies, and where its results go. Its report is templates/<name>/report.html.
    name: str
    config: type[Config]
    presets: dict[str, Config]
    noises: dict[str, Config]
    studies: Path
    output_root: Path

    @abstractmethod
    def simulate(self, config: Config, payload: str) -> Transmission: ...

    @abstractmethod
    def measure(
        self, config: Config, transmission: Transmission, seconds: float
    ) -> RunMetrics: ...

    @abstractmethod
    def parameters(self, config: Config) -> dict[str, str]:
        # The settings a report shows for one case, by name.
        ...

    @abstractmethod
    def symbols(self, config: Config) -> tuple[str, ...]:
        # The symbol labels, in the order of the counts in RunMetrics.
        ...

    @property
    def title(self) -> str:
        return self.name.capitalize()
