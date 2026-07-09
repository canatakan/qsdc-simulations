"""Benchmark execution engine."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from time import time
from typing import Any, Callable, TextIO

from qsdc.common.bits import chunk_bits
from qsdc.common.bits import weighted_random_bits
from qsdc.common.random import make_random_source
from qsdc.common.random.base import RandomSource
from qsdc.common.random.classical import ClassicalRandomSource
from qsdc.protocols.srikara.benchmark.config import BenchmarkConfig
from qsdc.protocols.srikara.benchmark.metrics import (
    aggregate_trial_metrics,
    summarize_checks,
    summarize_messages,
)
from qsdc.protocols.srikara.benchmark.artifacts.output import write_benchmark_artifacts
from qsdc.protocols.srikara.benchmark.seeds import derive_seed
from qsdc.protocols.srikara.simulator.backends import make_backend
from qsdc.protocols.srikara.simulator.backends.base import QSDCBackend
from qsdc.protocols.srikara.simulator.config import ProtocolConfig
from qsdc.protocols.srikara.simulator.distributions import SqueezeRDistribution
from qsdc.protocols.srikara.simulator.protocol import simulate_qsdc


BackendFactory = Callable[[str], QSDCBackend]
RandomSourceFactory = Callable[[str, int], RandomSource]


@dataclass(frozen=True)
class BenchmarkCombo:
    combo_index: int
    seed_index: int
    intervals: str
    one_probability: float
    r_distribution: SqueezeRDistribution


@dataclass(frozen=True)
class BenchmarkReport:
    output_dir: str
    effective_config: dict[str, object]
    summary: dict[str, object]
    trials: list[dict[str, object]]
    combos: list[dict[str, object]]


def run_benchmark(
    config: BenchmarkConfig,
    output_dir: str | None = None,
    write_artifacts: bool = True,
    progress: bool = False,
    progress_stream: TextIO | None = None,
    backend_factory: BackendFactory = make_backend,
    random_source_factory: RandomSourceFactory = make_random_source,
) -> BenchmarkReport:
    effective_config = config.with_output_dir(output_dir or config.output_dir)
    base_output_dir = effective_config.output_dir or str(
        Path("results") / "srikara" / "benchmark" / effective_config.name
    )
    effective_config = effective_config.with_output_dir(base_output_dir)
    benchmark_run_id = _benchmark_run_id()
    benchmark_run_dir = str(Path(base_output_dir) / benchmark_run_id)

    started_at = time()
    combos = _expand_combos(effective_config)
    trial_rows: list[dict[str, object]] = []
    combo_rows: list[dict[str, object]] = []
    progress_reporter = _ProgressReporter(
        enabled=progress,
        stream=progress_stream or sys.stderr,
        total_combos=len(combos),
        total_trials=len(combos) * effective_config.trials_per_combo,
    )

    for combo in combos:
        combo_trials = []
        for trial_index in range(effective_config.trials_per_combo):
            trial_row = _run_trial(
                effective_config,
                combo,
                trial_index,
                backend_factory,
                random_source_factory,
            )
            trial_rows.append(trial_row)
            combo_trials.append(trial_row)
            progress_reporter.trial_completed(combo.combo_index + 1)
        combo_rows.append(_aggregate_combo(effective_config, combo, combo_trials))

    accepted_count = sum(1 for trial in trial_rows if trial["accepted"])
    summary = {
        "name": effective_config.name,
        "benchmark_run_id": benchmark_run_id,
        "base_output_dir": base_output_dir,
        "output_dir": benchmark_run_dir,
        "parameters": {
            "backend": effective_config.backend,
            "random_source": effective_config.random_source,
            "tolerance_sigmas": effective_config.tolerance_sigmas,
            "interval_policies": list(effective_config.interval_policies),
            "check_axis_policy": effective_config.check_axis_policy,
            "message_axis_policy": effective_config.message_axis_policy,
            "one_probabilities": list(effective_config.one_probabilities),
            "r_distributions": [
                distribution.summary()
                for distribution in effective_config.r_distributions
            ],
            "alpha_distribution": effective_config.alpha_distribution.summary(),
            "theta_distribution": effective_config.theta_distribution.summary(),
        },
        "derived_counts": {
            "payload_bit_count": effective_config.payload_bit_count,
            "padding_bit_count": effective_config.padding_bit_count,
            "transmitted_message_bit_count": (
                effective_config.transmitted_message_bit_count
            ),
            "message_symbol_count": effective_config.message_symbol_count,
            "message_mode_count": effective_config.message_symbol_count,
            "n_states": effective_config.n_states,
        },
        "combo_count": len(combo_rows),
        "trial_count": len(trial_rows),
        "accepted_count": accepted_count,
        "accepted_rate": accepted_count / len(trial_rows) if trial_rows else 0.0,
        "elapsed_seconds": time() - started_at,
        "artifacts": {
            "benchmark": "benchmark.json",
            "combos_csv": "combos.csv",
            "trials_csv": "trials.csv",
            "html_report": "report.html",
            "html_report_css": "report.css",
            "plots": [],
        },
    }
    report = BenchmarkReport(
        output_dir=benchmark_run_dir,
        effective_config=effective_config.to_dict(),
        summary=summary,
        trials=trial_rows,
        combos=combo_rows,
    )
    if write_artifacts:
        progress_reporter.writing_artifacts()
        write_benchmark_artifacts(report)
    progress_reporter.finished()
    return report


def _benchmark_run_id() -> str:
    return f"run_{int(time())}"


class _ProgressReporter:
    def __init__(
        self,
        enabled: bool,
        stream: TextIO,
        total_combos: int,
        total_trials: int,
    ) -> None:
        self._enabled = enabled
        self._stream = stream
        self._total_combos = total_combos
        self._total_trials = total_trials
        self._completed_trials = 0

    def trial_completed(self, combo_number: int) -> None:
        if not self._enabled:
            return
        self._completed_trials += 1
        percent = (
            100.0 * self._completed_trials / self._total_trials
            if self._total_trials
            else 100.0
        )
        self._write(
            "\r"
            f"Running benchmark: {self._completed_trials}/{self._total_trials} "
            f"trials ({percent:5.1f}%), combo "
            f"{combo_number}/{self._total_combos}"
        )

    def writing_artifacts(self) -> None:
        if not self._enabled:
            return
        self._write("\nWriting artifacts...")

    def finished(self) -> None:
        if not self._enabled:
            return
        self._write("\rBenchmark run finished.                         \n")

    def _write(self, message: str) -> None:
        self._stream.write(message)
        self._stream.flush()


def _expand_combos(config: BenchmarkConfig) -> list[BenchmarkCombo]:
    combos: list[BenchmarkCombo] = []
    for intervals in config.interval_policies:
        for seed_index, (one_probability, r_distribution) in enumerate(
            product(
                config.one_probabilities,
                config.r_distributions,
            )
        ):
            combos.append(
                BenchmarkCombo(
                    combo_index=len(combos),
                    seed_index=seed_index,
                    intervals=intervals,
                    one_probability=one_probability,
                    r_distribution=r_distribution,
                )
            )
    return combos


def _run_trial(
    config: BenchmarkConfig,
    combo: BenchmarkCombo,
    trial_index: int,
    backend_factory: BackendFactory,
    random_source_factory: RandomSourceFactory,
) -> dict[str, object]:
    trial_seed = derive_seed(config.base_seed, combo.seed_index, trial_index)
    message_seed = derive_seed(trial_seed, "message")
    simulation_seed = derive_seed(trial_seed, "simulation")
    bits = weighted_random_bits(
        bit_count=config.payload_bit_count,
        one_probability=combo.one_probability,
        random_source=ClassicalRandomSource(message_seed),
    )
    symbols = chunk_bits(bits, 3)
    result = simulate_qsdc(
        symbols,
        config=ProtocolConfig.from_options(
            n_states=config.n_states,
            alpha_distribution=config.alpha_distribution,
            squeeze_r_distribution=combo.r_distribution,
            theta_distribution=config.theta_distribution,
            tolerance_sigmas=config.tolerance_sigmas,
            intervals=combo.intervals,
            check_axis_policy=config.check_axis_policy,
            message_axis_policy=config.message_axis_policy,
            seed=simulation_seed,
        ),
        backend=backend_factory(config.backend),
        random_source=random_source_factory(config.random_source, simulation_seed),
    )
    message_metrics = summarize_messages(
        result.messages,
        payload_bit_count=config.payload_bit_count,
    )
    control_metrics = summarize_checks(result.controls)
    decoy_metrics = summarize_checks(result.decoys)
    check_sigma_deviations = _check_sigma_deviations(
        (*result.controls, *result.decoys),
        result.measurement_noise_sigma,
    )
    return {
        "combo_index": combo.combo_index,
        "trial_index": trial_index,
        "trial_seed": trial_seed,
        "message_seed": message_seed,
        "simulation_seed": simulation_seed,
        "backend": result.backend_name,
        "random_source": result.random_source_name,
        "intervals": result.intervals,
        "check_axis_policy": result.check_axis_policy,
        "message_axis_policy": result.message_axis_policy,
        "one_probability": combo.one_probability,
        "check_tolerance_sigmas": result.check_tolerance_sigmas,
        "measurement_noise_sigma": result.measurement_noise_sigma,
        "r_distribution": combo.r_distribution.summary(),
        "r_distribution_config": combo.r_distribution.to_dict(),
        "alpha_distribution": config.alpha_distribution.summary(),
        "theta_distribution": config.theta_distribution.summary(),
        "payload_bit_count": config.payload_bit_count,
        "padding_bit_count": config.padding_bit_count,
        "transmitted_message_bit_count": config.transmitted_message_bit_count,
        "message_mode_count": config.message_symbol_count,
        "n_states": config.n_states,
        "control_passed": result.control_passed,
        "decoy_passed": result.decoy_passed,
        "accepted": result.accepted,
        **message_metrics,
        "control_check_count": control_metrics["check_count"],
        "control_failed_check_count": control_metrics["failed_check_count"],
        "control_mean_abs_deviation": control_metrics["mean_abs_deviation"],
        "control_max_abs_deviation": control_metrics["max_abs_deviation"],
        "decoy_check_count": decoy_metrics["check_count"],
        "decoy_failed_check_count": decoy_metrics["failed_check_count"],
        "decoy_mean_abs_deviation": decoy_metrics["mean_abs_deviation"],
        "decoy_max_abs_deviation": decoy_metrics["max_abs_deviation"],
        "check_sigma_deviations": check_sigma_deviations,
    }


def _check_sigma_deviations(
    checks: Any,
    measurement_noise_sigma: float,
) -> tuple[float, ...]:
    return tuple(
        abs(check.measured - check.expected) / measurement_noise_sigma
        for check in checks
    )


def _aggregate_combo(
    config: BenchmarkConfig,
    combo: BenchmarkCombo,
    trials: list[dict[str, object]],
) -> dict[str, Any]:
    accepted_count = sum(1 for trial in trials if trial["accepted"])
    control_pass_count = sum(1 for trial in trials if trial["control_passed"])
    decoy_pass_count = sum(1 for trial in trials if trial["decoy_passed"])
    control_check_count = sum(int(trial["control_check_count"]) for trial in trials)
    control_failed_check_count = sum(
        int(trial["control_failed_check_count"]) for trial in trials
    )
    decoy_check_count = sum(int(trial["decoy_check_count"]) for trial in trials)
    decoy_failed_check_count = sum(
        int(trial["decoy_failed_check_count"]) for trial in trials
    )
    all_metrics = aggregate_trial_metrics(trials)
    accepted_metrics = aggregate_trial_metrics(trials, accepted=True)
    rejected_metrics = aggregate_trial_metrics(trials, accepted=False)
    trial_count = len(trials)
    check_tolerance_sigmas = _single_trial_float(trials, "check_tolerance_sigmas")
    measurement_noise_sigma = _single_trial_float(trials, "measurement_noise_sigma")
    return {
        "combo_index": combo.combo_index,
        "one_probability": combo.one_probability,
        "r_distribution": combo.r_distribution.summary(),
        "r_distribution_config": combo.r_distribution.to_dict(),
        "alpha_distribution": config.alpha_distribution.summary(),
        "alpha_distribution_config": config.alpha_distribution.to_dict(),
        "theta_distribution": config.theta_distribution.summary(),
        "theta_distribution_config": config.theta_distribution.to_dict(),
        "intervals": combo.intervals,
        "trial_count": trial_count,
        "accepted_count": accepted_count,
        "accepted_rate": accepted_count / trial_count if trial_count else 0.0,
        "control_pass_rate": control_pass_count / trial_count if trial_count else 0.0,
        "decoy_pass_rate": decoy_pass_count / trial_count if trial_count else 0.0,
        "check_tolerance_sigmas": check_tolerance_sigmas,
        "measurement_noise_sigma": measurement_noise_sigma,
        "control_check_count": control_check_count,
        "control_failed_check_count": control_failed_check_count,
        "control_failed_check_rate": (
            control_failed_check_count / control_check_count
            if control_check_count
            else 0.0
        ),
        "control_mean_failed_check_count_per_trial": (
            control_failed_check_count / trial_count if trial_count else 0.0
        ),
        "control_max_failed_check_count_per_trial": max(
            (int(trial["control_failed_check_count"]) for trial in trials),
            default=0,
        ),
        "decoy_check_count": decoy_check_count,
        "decoy_failed_check_count": decoy_failed_check_count,
        "decoy_failed_check_rate": (
            decoy_failed_check_count / decoy_check_count
            if decoy_check_count
            else 0.0
        ),
        "decoy_mean_failed_check_count_per_trial": (
            decoy_failed_check_count / trial_count if trial_count else 0.0
        ),
        "decoy_max_failed_check_count_per_trial": max(
            (int(trial["decoy_failed_check_count"]) for trial in trials),
            default=0,
        ),
        "all": all_metrics,
        "accepted": accepted_metrics,
        "rejected": rejected_metrics,
    }


def _single_trial_float(
    trials: list[dict[str, object]],
    field: str,
) -> float | None:
    values = {float(trial[field]) for trial in trials}
    if not values:
        return None
    if len(values) != 1:
        raise ValueError(f"expected one {field} value per combo, got {values!r}")
    return next(iter(values))
