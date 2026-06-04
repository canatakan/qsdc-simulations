"""Configuration for the CV QSDC protocol simulation."""

from __future__ import annotations

from dataclasses import dataclass, field

from srikara.simulator.core.distributions import (
    AlphaDistribution,
    SqueezeRDistribution,
    ThetaDistribution,
    UniformSqueezeR,
    UniformSquareAlpha,
    UniformTheta,
)


DEFAULT_N_STATES = 8
DEFAULT_ALPHA_BOUND = 2.0
DEFAULT_SQUEEZE_R_MIN = 0.05
DEFAULT_SQUEEZE_R_MAX = 0.8
DEFAULT_SEED = 11
DEFAULT_EXACT_TOLERANCE = 1e-7
DEFAULT_SAMPLED_TOLERANCE_SIGMAS = 4.0


@dataclass(frozen=True)
class ProtocolConfig:
    """User-facing simulation settings."""

    n_states: int = DEFAULT_N_STATES
    alpha_distribution: AlphaDistribution = field(
        default_factory=lambda: UniformSquareAlpha(DEFAULT_ALPHA_BOUND)
    )
    squeeze_r_distribution: SqueezeRDistribution = field(
        default_factory=lambda: UniformSqueezeR(
            DEFAULT_SQUEEZE_R_MIN,
            DEFAULT_SQUEEZE_R_MAX,
        )
    )
    theta_distribution: ThetaDistribution = field(default_factory=UniformTheta)
    tolerance: float | None = None
    seed: int = DEFAULT_SEED


@dataclass(frozen=True)
class ResolvedProtocolConfig:
    """Simulation settings after backend defaults are applied."""

    n_states: int
    alpha_distribution: AlphaDistribution
    squeeze_r_distribution: SqueezeRDistribution
    theta_distribution: ThetaDistribution
    tolerance: float
    seed: int


def resolve_config(
    config: ProtocolConfig, backend, message_count: int
) -> ResolvedProtocolConfig:
    validate_config(config, message_count)
    tolerance = (
        backend.default_tolerance if config.tolerance is None else config.tolerance
    )
    return ResolvedProtocolConfig(
        n_states=config.n_states,
        alpha_distribution=config.alpha_distribution,
        squeeze_r_distribution=config.squeeze_r_distribution,
        theta_distribution=config.theta_distribution,
        tolerance=tolerance,
        seed=config.seed,
    )


def validate_config(config: ProtocolConfig, message_count: int) -> None:
    if config.n_states % 4 != 0:
        raise ValueError("n_states must be divisible by 4")
    expected_messages = config.n_states // 4
    if message_count != expected_messages:
        raise ValueError(
            f"expected {expected_messages} 3-bit symbols for n={config.n_states}, "
            f"got {message_count}"
        )
    if config.tolerance is not None and config.tolerance < 0:
        raise ValueError("tolerance must be non-negative")
