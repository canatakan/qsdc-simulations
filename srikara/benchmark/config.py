"""JSON config parsing for Srikara benchmark runs."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from itertools import count
from math import pi
from pathlib import Path
from typing import Any, Iterable, Protocol

from srikara.simulator.core.config import DEFAULT_ALPHA_BOUND
from srikara.simulator.core.distributions import (
    AlphaDistribution,
    FixedSqueezeR,
    FixedTheta,
    SqueezeRDistribution,
    ThetaDistribution,
    UniformSqueezeR,
    UniformSquareAlpha,
    UniformTheta,
)


class ToleranceSweep(Protocol):
    def expand(self) -> tuple[float, ...]:
        ...

    def to_dict(self) -> dict[str, object]:
        ...


@dataclass(frozen=True)
class ExplicitValues:
    values: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.values:
            raise ValueError("explicit tolerance sweep requires at least one value")
        for value in self.values:
            _validate_tolerance(value)

    def expand(self) -> tuple[float, ...]:
        return self.values

    def to_dict(self) -> dict[str, object]:
        return {"kind": "explicit", "values": list(self.values)}


@dataclass(frozen=True)
class LinearSweep:
    start: float
    stop: float
    step: float

    def __post_init__(self) -> None:
        _validate_tolerance(self.start)
        _validate_tolerance(self.stop)
        if self.step <= 0:
            raise ValueError("linear tolerance step must be positive")
        if self.stop < self.start:
            raise ValueError("linear tolerance stop must be >= start")

    def expand(self) -> tuple[float, ...]:
        values: list[float] = []
        epsilon = self.step / 1_000_000
        for index in count():
            value = self.start + index * self.step
            if value > self.stop + epsilon:
                break
            values.append(round(value, 12))
        return tuple(values)

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": "linear",
            "start": self.start,
            "stop": self.stop,
            "step": self.step,
        }


@dataclass(frozen=True)
class BenchmarkConfig:
    name: str
    backend: str
    random_source: str
    payload_bit_count: int
    trials_per_combo: int
    base_seed: int
    output_dir: str | None
    one_probabilities: tuple[float, ...]
    tolerances: ToleranceSweep
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

    def tolerance_values(self) -> tuple[float, ...]:
        return self.tolerances.expand()

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "backend": self.backend,
            "random_source": self.random_source,
            "payload_bit_count": self.payload_bit_count,
            "trials_per_combo": self.trials_per_combo,
            "base_seed": self.base_seed,
            "output_dir": self.output_dir,
            "one_probabilities": list(self.one_probabilities),
            "tolerances": self.tolerances.to_dict(),
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
            "output_dir",
            "one_probabilities",
            "tolerances",
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
        output_dir=_optional_str(raw.get("output_dir")),
        one_probabilities=_float_tuple(raw["one_probabilities"]),
        tolerances=_parse_tolerances(raw["tolerances"]),
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


def _parse_tolerances(raw: dict[str, Any]) -> ToleranceSweep:
    kind = raw.get("kind")
    if kind == "explicit":
        _reject_unknown_keys(raw, {"kind", "values"}, "tolerances")
        return ExplicitValues(_float_tuple(raw["values"]))
    if kind == "linear":
        _reject_unknown_keys(raw, {"kind", "start", "stop", "step"}, "tolerances")
        return LinearSweep(
            start=float(raw["start"]),
            stop=float(raw["stop"]),
            step=float(raw["step"]),
        )
    raise ValueError(f"unknown tolerance sweep kind {kind!r}")


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


def _validate_tolerance(value: float) -> None:
    if value < 0:
        raise ValueError("tolerance values must be non-negative")
