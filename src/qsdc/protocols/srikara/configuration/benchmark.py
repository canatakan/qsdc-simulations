"""Validated configuration consumed directly by Srikara benchmarks."""

from __future__ import annotations

from typing import Annotated, Optional

from pydantic import Field, model_validator

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
from qsdc.protocols.srikara.configuration.simulator import (
    AxisPolicy,
    BackendName,
    ErrorCorrection,
    IntervalPolicy,
    RandomSourceName,
    SimulatorConfig,
)


class BenchmarkConfig(ConfigModel):
    """Simple, serializable input for one benchmark run."""

    name: Annotated[str, Field(min_length=1)] = "benchmark"
    backend: BackendName = "sf-sampled"
    noise: NoiseConfig = Field(default_factory=NoiseConfig)
    random_source: RandomSourceName = "classical"
    payload_bit_count: PositiveInteger = 4096
    trials_per_combo: PositiveInteger = 1
    max_attempts_per_block: PositiveInteger = 1
    base_seed: NonNegativeInteger = 0
    tolerance_sigmas: NonNegativeFloat = 1.0
    interval_policies: Annotated[list[IntervalPolicy], Field(min_length=1)] = Field(
        default_factory=lambda: ["default"],
    )
    sigma_diagnostics: bool = False
    check_axis_policy: AxisPolicy = "random"
    message_axis_policy: AxisPolicy = "random"
    output_dir: Optional[str] = None
    one_probabilities: Annotated[list[Probability], Field(min_length=1)] = Field(
        default_factory=lambda: [0.5],
    )
    r_distributions: Annotated[list[SqueezeConfig], Field(min_length=1)] = Field(
        default_factory=lambda: [UniformSqueezeConfig()],
    )
    alpha_distribution: AlphaConfig = Field(default_factory=AlphaConfig)
    theta_distribution: ThetaConfig = Field(default_factory=UniformThetaConfig)
    error_correction: ErrorCorrection = "none"

    @model_validator(mode="after")
    def validate_retry_configuration(self) -> BenchmarkConfig:
        if self.max_attempts_per_block > 1 and self.error_correction == "none":
            raise ValueError("max_attempts_per_block > 1 requires SECDED")
        return self

    @property
    def padding_bit_count(self) -> int:
        if self.error_correction == "secded":
            return (-self.payload_bit_count) % 12
        return (-self.payload_bit_count) % 3

    @property
    def codec_padding_bit_count(self) -> int:
        if self.error_correction == "secded":
            return self.padding_bit_count
        return 0

    @property
    def modulation_padding_bit_count(self) -> int:
        if self.error_correction == "secded":
            return 0
        return self.padding_bit_count

    @property
    def transmitted_message_bit_count(self) -> int:
        if self.error_correction == "secded":
            return 2 * (self.payload_bit_count + self.codec_padding_bit_count)
        return self.payload_bit_count + self.modulation_padding_bit_count

    @property
    def message_symbol_count(self) -> int:
        return self.transmitted_message_bit_count // 3

    @property
    def n_states(self) -> int:
        return 4 * self.message_symbol_count

    @property
    def transport_block_count(self) -> int:
        if self.error_correction == "secded":
            return (self.payload_bit_count + self.codec_padding_bit_count) // 12
        return 1

    def with_output_dir(self, output_dir: Optional[str]) -> BenchmarkConfig:
        return self.model_copy(update={"output_dir": output_dir})

    def simulator_config(
        self,
        *,
        intervals: IntervalPolicy,
        squeeze_r_distribution: SqueezeConfig,
        seed: int,
    ) -> SimulatorConfig:
        """Project benchmark settings onto the simulator's strict input model."""

        return SimulatorConfig(
            backend=self.backend,
            noise=self.noise,
            random_source=self.random_source,
            alpha_distribution=self.alpha_distribution,
            squeeze_r_distribution=squeeze_r_distribution,
            theta_distribution=self.theta_distribution,
            tolerance_sigmas=self.tolerance_sigmas,
            intervals=intervals,
            check_axis_policy=self.check_axis_policy,
            message_axis_policy=self.message_axis_policy,
            seed=seed,
            error_correction=self.error_correction,
            max_attempts_per_block=self.max_attempts_per_block,
        )
