"""Configuration for the CV QSDC protocol simulation."""

from __future__ import annotations

from dataclasses import dataclass, field

from qsdc.protocols.srikara.simulator.distributions import (
    AlphaDistribution,
    SqueezeRDistribution,
    ThetaDistribution,
    UniformSqueezeR,
    UniformSquareAlpha,
    UniformTheta,
)
from qsdc.protocols.srikara.simulator.encoding import (
    DEFAULT_INTERVALS,
    INTERVAL_STRATEGIES,
)


DEFAULT_N_STATES = 8
DEFAULT_ALPHA_BOUND = 2.0
DEFAULT_SQUEEZE_R_MIN = 0.05
DEFAULT_SQUEEZE_R_MAX = 0.8
DEFAULT_SEED = 11
DEFAULT_EXACT_MEASUREMENT_NOISE_SIGMA = 1e-7
DEFAULT_EXACT_TOLERANCE_SIGMAS = 1.0
DEFAULT_SAMPLED_TOLERANCE_SIGMAS = 4.0
MESSAGE_AXIS_POLICIES = ("random", "optimized")
DEFAULT_MESSAGE_AXIS_POLICY = "random"
CHECK_AXIS_POLICIES = ("random", "optimized")
DEFAULT_CHECK_AXIS_POLICY = "random"


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
    tolerance_sigmas: float | None = None
    intervals: str = DEFAULT_INTERVALS
    check_axis_policy: str = DEFAULT_CHECK_AXIS_POLICY
    message_axis_policy: str = DEFAULT_MESSAGE_AXIS_POLICY
    seed: int = DEFAULT_SEED


@dataclass(frozen=True)
class ResolvedProtocolConfig:
    """Simulation settings after backend defaults are applied."""

    n_states: int
    alpha_distribution: AlphaDistribution
    squeeze_r_distribution: SqueezeRDistribution
    theta_distribution: ThetaDistribution
    tolerance_sigmas: float
    intervals: str
    check_axis_policy: str
    message_axis_policy: str
    seed: int


def resolve_config(
    config: ProtocolConfig, backend, message_count: int
) -> ResolvedProtocolConfig:
    validate_config(config, message_count)
    tolerance_sigmas = (
        backend.default_tolerance_sigmas
        if config.tolerance_sigmas is None
        else config.tolerance_sigmas
    )
    return ResolvedProtocolConfig(
        n_states=config.n_states,
        alpha_distribution=config.alpha_distribution,
        squeeze_r_distribution=config.squeeze_r_distribution,
        theta_distribution=config.theta_distribution,
        tolerance_sigmas=tolerance_sigmas,
        intervals=config.intervals,
        check_axis_policy=config.check_axis_policy,
        message_axis_policy=config.message_axis_policy,
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
    if config.tolerance_sigmas is not None and config.tolerance_sigmas < 0:
        raise ValueError("tolerance_sigmas must be non-negative")
    if config.intervals not in INTERVAL_STRATEGIES:
        allowed = ", ".join(repr(strategy) for strategy in INTERVAL_STRATEGIES)
        raise ValueError(f"intervals must be one of {allowed}")
    if config.check_axis_policy not in CHECK_AXIS_POLICIES:
        allowed = ", ".join(repr(policy) for policy in CHECK_AXIS_POLICIES)
        raise ValueError(f"check_axis_policy must be one of {allowed}")
    if config.message_axis_policy not in MESSAGE_AXIS_POLICIES:
        allowed = ", ".join(repr(policy) for policy in MESSAGE_AXIS_POLICIES)
        raise ValueError(f"message_axis_policy must be one of {allowed}")
