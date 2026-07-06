"""JSON config parsing for Srikara benchmark runs."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

from qsdc.protocols.srikara.configuration import (
    BENCHMARK_PARAMETERS,
    OPTIMIZATION_PARAMETERS,
    ParameterSet,
    RUN_PARAMETERS,
    SIMULATOR_PARAMETERS,
)
from qsdc.protocols.srikara.simulator.distributions import (
    AlphaDistribution,
    SqueezeRDistribution,
    ThetaDistribution,
)


@dataclass(frozen=True)
class BenchmarkConfig:
    name: str
    backend: str
    random_source: str
    payload_bit_count: int
    trials_per_combo: int
    base_seed: int
    tolerance_sigmas: float
    interval_policies: list[str]
    check_axis_policy: str
    message_axis_policy: str
    output_dir: str | None
    one_probabilities: list[float]
    r_distributions: list[SqueezeRDistribution]
    alpha_distribution: AlphaDistribution
    theta_distribution: ThetaDistribution

    def __post_init__(self) -> None:
        type(self).parameters().validate(self)

    @classmethod
    def parameters(cls) -> ParameterSet:
        return ParameterSet([
            *BENCHMARK_PARAMETERS,
            *RUN_PARAMETERS,
            OPTIMIZATION_PARAMETERS.parameter("check_axis_policy"),
            OPTIMIZATION_PARAMETERS.parameter("message_axis_policy"),
            SIMULATOR_PARAMETERS.parameter("tolerance_sigmas"),
            SIMULATOR_PARAMETERS.parameter("alpha_distribution"),
            SIMULATOR_PARAMETERS.parameter("theta_distribution"),
        ])

    @classmethod
    def from_options(cls, **overrides: object) -> "BenchmarkConfig":
        return cls(**cls.parameters().options(**overrides))

    @property
    def padding_bit_count(self) -> int:
        return (-self.payload_bit_count) % 3

    @property
    def transmitted_message_bit_count(self) -> int:
        return self.payload_bit_count + self.padding_bit_count

    @property
    def message_symbol_count(self) -> int:
        return self.transmitted_message_bit_count // 3

    @property
    def n_states(self) -> int:
        return 4 * self.message_symbol_count

    def with_output_dir(self, output_dir: str | None) -> "BenchmarkConfig":
        return replace(self, output_dir=output_dir)

    def to_dict(self) -> dict[str, object]:
        return type(self).parameters().to_dict(self)


def load_benchmark_json(path: str | Path) -> BenchmarkConfig:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        raise ValueError("benchmark config must be a JSON object")
    return BenchmarkConfig.from_options(**raw)
