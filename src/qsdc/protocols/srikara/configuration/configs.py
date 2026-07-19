"""Top-level Srikara protocol and benchmark configurations."""

from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import Field, TypeAdapter, field_serializer, field_validator

from qsdc.protocols.srikara.configuration.models import (
    BaseSqueezeConfigModel,
    BaseThetaConfigModel,
    ConfigurationModel,
    NonNegativeFloat,
    NonNegativeInteger,
    NoiseConfig,
    PositiveInteger,
    Probability,
    SqueezeConfig,
    ThetaConfig,
    UniformSquareAlphaConfig,
)
from qsdc.protocols.srikara.simulator.distributions import (
    FixedSqueezeR,
    FixedTheta,
    UniformSqueezeR,
    UniformSquareAlpha,
    UniformTheta,
)
from qsdc.protocols.srikara.simulator.noise import NoiseModel


class BaseSimulationConfig(ConfigurationModel):
    """Runtime-valued fields shared by protocol and benchmark configuration."""

    alpha_distribution: UniformSquareAlpha = Field(
        default_factory=lambda: UniformSquareAlpha(bound=2.0),
    )
    theta_distribution: Union[UniformTheta, FixedTheta] = Field(
        default_factory=UniformTheta,
    )
    tolerance_sigmas: NonNegativeFloat = 1.0
    check_axis_policy: Literal["random", "optimized"] = "random"
    message_axis_policy: Literal["random", "optimized"] = "random"

    @field_validator("alpha_distribution", mode="before")
    @classmethod
    def build_alpha_distribution(cls, value: object) -> UniformSquareAlpha:
        if isinstance(value, UniformSquareAlpha):
            return value
        return UniformSquareAlphaConfig.model_validate(value).build()

    @field_validator("theta_distribution", mode="before")
    @classmethod
    def build_theta_distribution(
        cls,
        value: object,
    ) -> UniformTheta | FixedTheta:
        if isinstance(value, (UniformTheta, FixedTheta)):
            return value
        return TypeAdapter(ThetaConfig).validate_python(value).build()

    @field_serializer("alpha_distribution")
    def serialize_alpha_distribution(
        self,
        value: UniformSquareAlpha,
    ) -> dict[str, object]:
        return UniformSquareAlphaConfig.from_runtime(value).model_dump(mode="json")

    @field_serializer("theta_distribution")
    def serialize_theta_distribution(
        self,
        value: UniformTheta | FixedTheta,
    ) -> dict[str, object]:
        return BaseThetaConfigModel.from_runtime(value).model_dump(mode="json")


class ProtocolConfig(BaseSimulationConfig):
    """Validated, executable configuration for one protocol simulation."""

    n_states: PositiveInteger = 8
    squeeze_r_distribution: Union[UniformSqueezeR, FixedSqueezeR] = Field(
        default_factory=lambda: UniformSqueezeR(lower=0.115, upper=0.576),
    )
    intervals: Literal[
        "default",
        "optimized_v4",
        "optimized_v8",
        "optimized_v12",
    ] = "default"
    seed: NonNegativeInteger = 11

    @field_validator("squeeze_r_distribution", mode="before")
    @classmethod
    def build_squeeze_distribution(
        cls,
        value: object,
    ) -> UniformSqueezeR | FixedSqueezeR:
        if isinstance(value, (UniformSqueezeR, FixedSqueezeR)):
            return value
        return TypeAdapter(SqueezeConfig).validate_python(value).build()

    @field_serializer("squeeze_r_distribution")
    def serialize_squeeze_distribution(
        self,
        value: UniformSqueezeR | FixedSqueezeR,
    ) -> dict[str, object]:
        return BaseSqueezeConfigModel.from_runtime(value).model_dump(mode="json")

    @classmethod
    def from_options(cls, **overrides: object) -> "ProtocolConfig":
        return cls.model_validate(overrides)

    def to_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class BenchmarkConfig(BaseSimulationConfig):
    """Validated, executable benchmark configuration."""

    name: Annotated[str, Field(min_length=1)] = "benchmark"
    backend: Literal["analytic", "sf", "sf-sampled", "sf-noise"] = "sf-sampled"
    noise: NoiseModel = Field(default_factory=NoiseModel)
    random_source: Literal["classical", "sf-bs-qrng"] = "classical"
    payload_bit_count: PositiveInteger = 4096
    trials_per_combo: PositiveInteger = 1
    base_seed: NonNegativeInteger = 0
    interval_policies: Annotated[list[str], Field(min_length=1)] = Field(
        default_factory=lambda: ["default"],
    )
    sigma_diagnostics: bool = False
    output_dir: Optional[str] = None
    one_probabilities: Annotated[list[Probability], Field(min_length=1)] = Field(
        default_factory=lambda: [0.5],
    )
    r_distributions: Annotated[
        list[Union[UniformSqueezeR, FixedSqueezeR]],
        Field(min_length=1),
    ] = Field(
        default_factory=lambda: [
            UniformSqueezeR(lower=0.115, upper=0.576)
        ],
    )

    @field_validator("noise", mode="before")
    @classmethod
    def build_noise(cls, value: object) -> NoiseModel:
        if value is None:
            return NoiseModel()
        if isinstance(value, NoiseModel):
            return value
        return NoiseConfig.model_validate(value).build()

    @field_validator("r_distributions", mode="before")
    @classmethod
    def build_squeeze_distributions(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        adapter = TypeAdapter(SqueezeConfig)
        return [
            distribution
            if isinstance(distribution, (UniformSqueezeR, FixedSqueezeR))
            else adapter.validate_python(distribution).build()
            for distribution in value
        ]

    @field_serializer("noise")
    def serialize_noise(self, value: NoiseModel) -> dict[str, object]:
        return NoiseConfig.from_runtime(value).model_dump(mode="json")

    @field_serializer("r_distributions")
    def serialize_squeeze_distributions(
        self,
        value: list[Union[UniformSqueezeR, FixedSqueezeR]],
    ) -> list[dict[str, object]]:
        return [
            BaseSqueezeConfigModel.from_runtime(distribution).model_dump(
                mode="json",
            )
            for distribution in value
        ]

    @classmethod
    def from_options(cls, **overrides: object) -> "BenchmarkConfig":
        return cls.model_validate(overrides)

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

    def to_dict(self) -> dict[str, object]:
        data = self.model_dump(mode="json", exclude_none=True)
        if not any(self.noise.stages.values()):
            data.pop("noise")
        return data
