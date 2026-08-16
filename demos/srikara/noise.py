"""Compare Srikara loss and noise mechanisms with hand-checkable moments."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from math import sqrt

import numpy as np
import strawberryfields as sf

from qsdc.protocols.srikara.configuration.noise import (
    DetectorInefficiencyConfig,
    ElectronicNoiseConfig,
    NoiseConfig,
    PureLossConfig,
    ThermalLossConfig,
)
from qsdc.common.quadrature import QuadratureAxis
from qsdc.protocols.srikara.simulator.backends import make_backend
VACUUM_VARIANCE = 0.25


NoiseValues = dict[str, list[dict[str, object]]]


@dataclass(frozen=True)
class Scenario:
    name: str
    noise: NoiseValues


@dataclass(frozen=True)
class Moments:
    mean: float
    variance: float


@dataclass(frozen=True)
class ScenarioResult:
    scenario: Scenario
    expected: Moments
    calibrated: Moments
    samples: np.ndarray

    @property
    def sampled(self) -> Moments:
        return Moments(
            mean=float(np.mean(self.samples)),
            variance=float(np.var(self.samples, ddof=1)),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--samples",
        type=int,
        default=50,
        help="one-shot measurements per scenario",
    )
    parser.add_argument("--seed", type=int, default=20260720)
    args = parser.parse_args()
    if args.samples < 2:
        parser.error("--samples must be at least 2")

    # With r=0, q means can be followed without squeeze transformations:
    # Bob sends alpha, Alice adds beta, and Bob measures alpha + beta.
    alpha = 1.5 + 0.0j
    beta = 0.75 + 0.75j
    scenarios = build_scenarios()
    results = [
        run_scenario(
            scenario,
            alpha=alpha,
            beta=beta,
            samples=args.samples,
            seed=args.seed + index,
        )
        for index, scenario in enumerate(scenarios)
    ]

    print_introduction(alpha, beta, args.samples)
    print_protocol_diagram()
    print_stage_matrix(scenarios)
    for result in results:
        print_calculation(result.scenario, alpha.real, beta.real)
    print_summary(results)


def build_scenarios() -> tuple[Scenario, ...]:
    """Return one isolated example per mechanism plus a combined channel."""

    return (
        Scenario("SF shot-noise baseline", {}),
        Scenario(
            "Forward pure loss",
            {"forward": [{"type": "loss", "transmittance": 0.64}]},
        ),
        Scenario(
            "Alice delay pure loss",
            {"alice_delay": [{"type": "loss", "transmittance": 0.64}]},
        ),
        Scenario(
            "Return pure loss",
            {"return_path": [{"type": "loss", "transmittance": 0.64}]},
        ),
        Scenario(
            "Return thermal loss",
            {
                "return_path": [
                    {
                        "type": "thermal_loss",
                        "transmittance": 0.64,
                        "environment_nbar": 0.5,
                    }
                ]
            },
        ),
        Scenario(
            "Detector inefficiency",
            {
                "bob_detector": [
                    {"type": "detector_inefficiency", "efficiency": 0.64}
                ]
            },
        ),
        Scenario(
            "Electronic readout noise",
            {
                "bob_readout": [
                    {"type": "electronic_noise", "variance_snu": 0.5}
                ]
            },
        ),
        Scenario(
            "Combined",
            {
                "forward": [{"type": "loss", "transmittance": 0.81}],
                "alice_delay": [
                    {"type": "loss", "transmittance": 0.81}
                ],
                "return_path": [
                    {
                        "type": "thermal_loss",
                        "transmittance": 0.64,
                        "environment_nbar": 0.5,
                    }
                ],
                "bob_detector": [
                    {"type": "detector_inefficiency", "efficiency": 0.64}
                ],
                "bob_readout": [
                    {"type": "electronic_noise", "variance_snu": 0.5}
                ],
            },
        ),
    )


def run_scenario(
    scenario: Scenario,
    alpha: complex,
    beta: complex,
    samples: int,
    seed: int,
) -> ScenarioResult:
    """Sample independent modes through the real configured SF backend."""

    config = NoiseConfig.model_validate(scenario.noise)
    backend = make_backend("sf-noise", config)
    backend.begin_run(seed)
    measured = np.array([
        backend.returned_measurement(
            alpha=alpha,
            squeeze_r=0.0,
            theta=0.0,
            beta=beta,
            axis=QuadratureAxis.Q,
        )
        for _ in range(samples)
    ])
    expected, _ = calculate_expected_moments(config, alpha.real, beta.real)
    calibrated_expectation = backend.returned_expectation(
        alpha=alpha,
        squeeze_r=0.0,
        theta=0.0,
        axis=QuadratureAxis.Q,
    )
    calibrated = Moments(
        mean=(
            calibrated_expectation.mean
            + backend.message_response_factor(0.0, 0.0, QuadratureAxis.Q)
            * beta.real
        ),
        variance=calibrated_expectation.sigma ** 2,
    )
    return ScenarioResult(scenario, expected, calibrated, measured)


def calculate_expected_moments(
    noise: NoiseConfig,
    alpha_q: float,
    beta_q: float,
) -> tuple[Moments, list[str]]:
    """Calculate expected moments without generating simulator samples."""

    mean = alpha_q
    variance = VACUUM_VARIANCE
    steps = [
        f"input coherent mode: mean={mean:.4f}, variance={variance:.4f}"
    ]

    for effect in noise.forward:
        mean, variance, formula = apply_effect_to_moments(effect, mean, variance)
        steps.append(f"forward {formula}")

    for effect in noise.alice_delay:
        mean, variance, formula = apply_effect_to_moments(effect, mean, variance)
        steps.append(f"Alice delay {formula}")

    mean += beta_q
    steps.append(f"Alice displacement: mean += {beta_q:.4f} -> {mean:.4f}")

    for effect in noise.return_path:
        mean, variance, formula = apply_effect_to_moments(effect, mean, variance)
        steps.append(f"return {formula}")

    for effect in noise.bob_detector:
        mean, variance, formula = apply_effect_to_moments(effect, mean, variance)
        steps.append(f"detector {formula}")

    for effect in noise.bob_readout:
        mean, variance, formula = apply_effect_to_moments(effect, mean, variance)
        steps.append(f"readout {formula}")

    return Moments(mean, variance), steps


def apply_effect_to_moments(
    effect: object,
    mean: float,
    variance: float,
) -> tuple[float, float, str]:
    """Apply one effect's standard first- and second-moment formulas."""

    if isinstance(effect, PureLossConfig):
        transmittance = effect.transmittance
        output_mean = sqrt(transmittance) * mean
        output_variance = (
            transmittance * variance
            + (1.0 - transmittance) * VACUUM_VARIANCE
        )
        formula = (
            f"pure loss T={transmittance:g}: "
            f"mean=sqrt(T)*mean={output_mean:.4f}, "
            f"variance=T*variance+(1-T)*Vvac={output_variance:.4f}"
        )
        return output_mean, output_variance, formula

    if isinstance(effect, ThermalLossConfig):
        transmittance = effect.transmittance
        thermal_variance = (2.0 * effect.environment_nbar + 1.0) * VACUUM_VARIANCE
        output_mean = sqrt(transmittance) * mean
        output_variance = (
            transmittance * variance
            + (1.0 - transmittance) * thermal_variance
        )
        formula = (
            f"thermal loss T={transmittance:g}, nbar={effect.environment_nbar:g}: "
            f"mean=sqrt(T)*mean={output_mean:.4f}, "
            f"variance=T*variance+(1-T)*(2*nbar+1)*Vvac="
            f"{output_variance:.4f}"
        )
        return output_mean, output_variance, formula

    if isinstance(effect, DetectorInefficiencyConfig):
        efficiency = effect.efficiency
        output_mean = sqrt(efficiency) * mean
        output_variance = (
            efficiency * variance
            + (1.0 - efficiency) * VACUUM_VARIANCE
        )
        formula = (
            f"inefficiency eta={efficiency:g}: "
            f"mean=sqrt(eta)*mean={output_mean:.4f}, "
            f"variance=eta*variance+(1-eta)*Vvac={output_variance:.4f}"
        )
        return output_mean, output_variance, formula

    if isinstance(effect, ElectronicNoiseConfig):
        added_variance = effect.variance_snu * VACUUM_VARIANCE
        output_variance = variance + added_variance
        formula = (
            f"electronic noise xi={effect.variance_snu:g} SNU: mean unchanged, "
            f"variance += xi*Vvac={output_variance:.4f}"
        )
        return mean, output_variance, formula

    raise TypeError(f"unsupported effect {type(effect).__name__!r}")


def print_introduction(alpha: complex, beta: complex, sample_count: int) -> None:
    print("Srikara physical loss/noise demonstration")
    print("=" * 42)
    print("Actual data: one MeasureHomodyne execution per independent optical mode")
    print("Expected data: standard Gaussian first/second-moment formulas")
    print(
        f"Strawberry Fields hbar={sf.hbar:g}; quadratures are divided by "
        "sqrt(2*hbar)"
    )
    print(f"Reported vacuum variance Vvac = {VACUUM_VARIANCE:g}")
    print(f"alpha_q = {alpha.real:g}; Alice beta_q = {beta.real:g}; r = 0")
    print(f"One-shot samples per scenario = {sample_count}")


def print_protocol_diagram() -> None:
    print(
        r"""

Noise placement in the implemented protocol
===========================================

 Bob prepares D(alpha) -> S(-r)
                 |
                 v
        [ FORWARD CHANNEL ]          PureLoss or ThermalLoss
                 |
                 v
              Alice
                 |
        +--------+-----------------------------+
        |                                      |
        | control mode                         | delayed mode
        v                                      v
      S(+r)                           [ ALICE OPTICAL DELAY ]
        |                              PureLoss or ThermalLoss
 [ ALICE DETECTOR ]                            |
 DetectorInefficiency                  D(beta) for a message
        |                                      |
 MeasureHomodyne                       [ RETURN CHANNEL ]
        |                              PureLoss or ThermalLoss
 [ ALICE READOUT ]                             |
 ElectronicNoise                             Bob
                                               |
                                             S(+r)
                                               |
                                        [ BOB DETECTOR ]
                                        DetectorInefficiency
                                               |
                                        MeasureHomodyne
                                               |
                                        [ BOB READOUT ]
                                        ElectronicNoise

The delay is a protocol hold; its configured physical storage loss is inserted
into the Strawberry Fields circuit only for delayed modes. Every other optical
box is also inserted into the SF circuit. Readout noise is applied once to the
classical value after MeasureHomodyne.
The same configured circuit supplies the calibrated mean and sigma used by
control and decoy checks; only residual deviation is treated as disturbance.
"""
    )


def print_stage_matrix(scenarios: tuple[Scenario, ...]) -> None:
    stages = (
        ("forward", "forward"),
        ("alice_delay", "A delay"),
        ("return_path", "return"),
        ("alice_detector", "A detector"),
        ("alice_readout", "A readout"),
        ("bob_detector", "B detector"),
        ("bob_readout", "B readout"),
    )
    print("Configured effects by scenario")
    print("=" * 30)
    print(f"{'scenario':<28} " + "  ".join(f"{label:<10}" for _, label in stages))
    print("-" * 111)
    for scenario in scenarios:
        noise = NoiseConfig.model_validate(scenario.noise)
        values = [stage_effects(noise, stage) for stage, _ in stages]
        print(
            f"{scenario.name:<28} "
            + "  ".join(f"{value:<10}" for value in values)
        )


def stage_effects(noise: NoiseConfig, stage: str) -> str:
    effects = getattr(noise, stage)
    if not effects:
        return "-"
    labels = {
        PureLossConfig: "pure",
        ThermalLossConfig: "thermal",
        DetectorInefficiencyConfig: "detector",
        ElectronicNoiseConfig: "electronic",
    }
    return ", ".join(labels[type(effect)] for effect in effects)


def print_calculation(scenario: Scenario, alpha_q: float, beta_q: float) -> None:
    noise = NoiseConfig.model_validate(scenario.noise)
    _, steps = calculate_expected_moments(noise, alpha_q, beta_q)
    print(f"\n{scenario.name}")
    print("-" * len(scenario.name))
    for step in steps:
        print(f"  {step}")


def print_summary(results: list[ScenarioResult]) -> None:
    print("\nCalculated moments, calibrated SF expectations, and sampled moments")
    print("-" * 99)
    print(
        "scenario                       calc mean     SF mean  sample mean  "
        "calc var      SF var  sample var"
    )
    for result in results:
        sampled = result.sampled
        print(
            f"{result.scenario.name:<28} "
            f"{result.expected.mean:>11.4f} "
            f"{result.calibrated.mean:>11.4f} "
            f"{sampled.mean:>12.4f} "
            f"{result.expected.variance:>9.4f} "
            f"{result.calibrated.variance:>11.4f} "
            f"{sampled.variance:>10.4f}"
        )


if __name__ == "__main__":
    main()
