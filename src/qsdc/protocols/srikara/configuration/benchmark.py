"""Validated configuration consumed directly by Srikara benchmarks."""

from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import Field

from qsdc.protocols.srikara.configuration.common import (
    ConfigModel,
    NonNegativeFloat,
    NonNegativeInteger,
    PositiveInteger,
    Probability,
)
from qsdc.protocols.srikara.configuration.distribution import (
    AlphaConfig,
    SqueezeConfig,
    ThetaConfig,
    UniformSqueezeConfig,
    UniformThetaConfig,
)
from qsdc.protocols.srikara.configuration.noise import NoiseConfig


class BenchmarkConfig(ConfigModel):
    """Simple, serializable input for one benchmark run."""

    name: Annotated[str, Field(min_length=1)] = "benchmark"
    backend: Literal["analytic", "sf", "sf-sampled", "sf-noise"] = "sf-sampled"
    noise: NoiseConfig = Field(default_factory=NoiseConfig)
    random_source: Literal["classical", "sf-bs-qrng"] = "classical"
    payload_bit_count: PositiveInteger = 4096
    trials_per_combo: PositiveInteger = 1
    base_seed: NonNegativeInteger = 0
    tolerance_sigmas: NonNegativeFloat = 1.0
    interval_policies: Annotated[list[str], Field(min_length=1)] = Field(
        default_factory=lambda: ["default"],
    )
    sigma_diagnostics: bool = False
    check_axis_policy: Literal["random", "optimized"] = "random"
    message_axis_policy: Literal["random", "optimized"] = "random"
    output_dir: Optional[str] = None
    one_probabilities: Annotated[list[Probability], Field(min_length=1)] = Field(
        default_factory=lambda: [0.5],
    )
    r_distributions: Annotated[list[SqueezeConfig], Field(min_length=1)] = Field(
        default_factory=lambda: [UniformSqueezeConfig()],
    )
    alpha_distribution: AlphaConfig = Field(default_factory=AlphaConfig)
    theta_distribution: ThetaConfig = Field(default_factory=UniformThetaConfig)

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

    def with_output_dir(self, output_dir: Optional[str]) -> "BenchmarkConfig":
        return self.model_copy(update={"output_dir": output_dir})
