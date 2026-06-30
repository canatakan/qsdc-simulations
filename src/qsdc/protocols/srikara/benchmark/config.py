"""JSON config parsing for Srikara benchmark runs."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from math import pi
from pathlib import Path
from typing import Any, Iterable

from qsdc.protocols.srikara.simulator.config import (
    CHECK_AXIS_POLICIES,
    DEFAULT_ALPHA_BOUND,
    DEFAULT_CHECK_AXIS_POLICY,
    DEFAULT_MESSAGE_AXIS_POLICY,
    MESSAGE_AXIS_POLICIES,
)
from qsdc.protocols.srikara.simulator.distributions import (
    AlphaDistribution,
    FixedSqueezeR,
    FixedTheta,
    SqueezeRDistribution,
    ThetaDistribution,
    UniformSqueezeR,
    UniformSquareAlpha,
    UniformTheta,
)


@dataclass(frozen=True)
class BenchmarkConfig:
    name: str
    backend: str
    random_source: str
    payload_bit_count: int
    trials_per_combo: int
    base_seed: int
    tolerance_sigmas: float | None
    check_axis_policy: str
    message_axis_policy: str
    output_dir: str | None
    one_probabilities: tuple[float, ...]
    r_distributions: tuple[SqueezeRDistribution, ...]
    alpha_distribution: AlphaDistribution
    theta_distribution: ThetaDistribution

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("benchmark name is required")
        if self.payload_bit_count <= 0:
            raise ValueError("payload_bit_count must be positive")
        if self.trials_per_combo <= 0:
            raise ValueError("trials_per_combo must be positive")
        if self.tolerance_sigmas is not None and self.tolerance_sigmas < 0:
            raise ValueError("tolerance_sigmas must be non-negative")
        if self.check_axis_policy not in CHECK_AXIS_POLICIES:
            allowed = ", ".join(repr(policy) for policy in CHECK_AXIS_POLICIES)
            raise ValueError(f"check_axis_policy must be one of {allowed}")
        if self.message_axis_policy not in MESSAGE_AXIS_POLICIES:
            allowed = ", ".join(repr(policy) for policy in MESSAGE_AXIS_POLICIES)
            raise ValueError(f"message_axis_policy must be one of {allowed}")
        if not self.one_probabilities:
            raise ValueError("one_probabilities must not be empty")
        for probability in self.one_probabilities:
            if not 0.0 <= probability <= 1.0:
                raise ValueError("one_probability values must be between 0 and 1")
        if not self.r_distributions:
            raise ValueError("r_distributions must not be empty")

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
        return {
            "name": self.name,
            "backend": self.backend,
            "random_source": self.random_source,
            "payload_bit_count": self.payload_bit_count,
            "trials_per_combo": self.trials_per_combo,
            "base_seed": self.base_seed,
            "tolerance_sigmas": self.tolerance_sigmas,
            "check_axis_policy": self.check_axis_policy,
            "message_axis_policy": self.message_axis_policy,
            "output_dir": self.output_dir,
            "one_probabilities": list(self.one_probabilities),
            "r_distributions": [
                distribution.to_dict() for distribution in self.r_distributions
            ],
            "alpha_distribution": self.alpha_distribution.to_dict(),
            "theta_distribution": self.theta_distribution.to_dict(),
        }


def load_benchmark_config(path: str | Path) -> BenchmarkConfig:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        raise ValueError("benchmark config must be a JSON object")
    return parse_benchmark_config(raw)


def parse_benchmark_config(raw: dict[str, Any]) -> BenchmarkConfig:
    _reject_unknown_keys(
        raw,
        {
            "name",
            "backend",
            "random_source",
            "payload_bit_count",
            "trials_per_combo",
            "base_seed",
            "tolerance_sigmas",
            "check_axis_policy",
            "message_axis_policy",
            "output_dir",
            "one_probabilities",
            "r_distributions",
            "alpha_distribution",
            "theta_distribution",
        },
        "benchmark config",
    )
    return BenchmarkConfig(
        name=str(raw.get("name", "benchmark")),
        backend=str(raw.get("backend", "sf-sampled")),
        random_source=str(raw.get("random_source", "classical")),
        payload_bit_count=_parse_payload_bit_count(raw),
        trials_per_combo=int(raw.get("trials_per_combo", 1)),
        base_seed=int(raw.get("base_seed", 0)),
        tolerance_sigmas=_optional_float(raw.get("tolerance_sigmas")),
        check_axis_policy=str(raw.get("check_axis_policy", DEFAULT_CHECK_AXIS_POLICY)),
        message_axis_policy=str(
            raw.get("message_axis_policy", DEFAULT_MESSAGE_AXIS_POLICY)
        ),
        output_dir=_optional_str(raw.get("output_dir")),
        one_probabilities=_float_tuple(raw["one_probabilities"]),
        r_distributions=tuple(
            _parse_r_distribution(item) for item in raw["r_distributions"]
        ),
        alpha_distribution=_parse_alpha_distribution(
            raw.get(
                "alpha_distribution",
                {"kind": "uniform_square", "bound": DEFAULT_ALPHA_BOUND},
            )
        ),
        theta_distribution=_parse_theta_distribution(
            raw.get("theta_distribution", {"kind": "uniform"})
        ),
    )


def _parse_payload_bit_count(raw: dict[str, Any]) -> int:
    if "payload_bit_count" not in raw:
        raise ValueError("payload_bit_count is required")
    return int(raw["payload_bit_count"])


def _parse_r_distribution(raw: dict[str, Any]) -> SqueezeRDistribution:
    kind = raw.get("kind")
    if kind == "uniform":
        _reject_unknown_keys(raw, {"kind", "lower", "upper"}, "r_distribution")
        return UniformSqueezeR(lower=float(raw["lower"]), upper=float(raw["upper"]))
    if kind == "fixed":
        _reject_unknown_keys(raw, {"kind", "value"}, "r_distribution")
        return FixedSqueezeR(value=float(raw["value"]))
    raise ValueError(f"unknown r distribution kind {kind!r}")


def _parse_alpha_distribution(raw: dict[str, Any]) -> AlphaDistribution:
    kind = raw.get("kind")
    if kind == "uniform_square":
        _reject_unknown_keys(raw, {"kind", "bound"}, "alpha_distribution")
        return UniformSquareAlpha(bound=float(raw["bound"]))
    raise ValueError(f"unknown alpha distribution kind {kind!r}")


def _parse_theta_distribution(raw: dict[str, Any]) -> ThetaDistribution:
    kind = raw.get("kind")
    if kind == "uniform":
        _reject_unknown_keys(
            raw,
            {"kind", "lower_pi", "upper_pi"},
            "theta_distribution",
        )
        return UniformTheta(
            lower=float(raw.get("lower_pi", 0.0)) * pi,
            upper=float(raw.get("upper_pi", 2.0)) * pi,
        )
    if kind == "fixed":
        _reject_unknown_keys(raw, {"kind", "value_pi"}, "theta_distribution")
        return FixedTheta(value=float(raw["value_pi"]) * pi)
    raise ValueError(f"unknown theta distribution kind {kind!r}")


def _reject_unknown_keys(
    raw: dict[str, Any],
    allowed_keys: set[str],
    context: str,
) -> None:
    unknown_keys = sorted(set(raw) - allowed_keys)
    if unknown_keys:
        joined = ", ".join(repr(key) for key in unknown_keys)
        raise ValueError(f"unknown {context} field(s): {joined}")


def _float_tuple(values: Iterable[object]) -> tuple[float, ...]:
    return tuple(float(value) for value in values)


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)
