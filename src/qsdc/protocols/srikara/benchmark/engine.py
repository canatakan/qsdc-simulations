"""Typed benchmark execution engine."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from time import time
from typing import TextIO

from qsdc.common.bits import weighted_random_bits
from qsdc.common.random.classical import ClassicalRandomSource
from qsdc.protocols.srikara.benchmark.artifacts.metrics import (
    BenchmarkCombo,
    BenchmarkRun,
    BenchmarkTrial,
)
from qsdc.protocols.srikara.benchmark.artifacts.output import write_benchmark_artifacts
from qsdc.protocols.srikara.benchmark.seeds import derive_seed
from qsdc.protocols.srikara.configuration.benchmark import BenchmarkConfig
from qsdc.protocols.srikara.configuration.distribution import SqueezeConfig
from qsdc.protocols.srikara.configuration.simulator import IntervalPolicy
from qsdc.protocols.srikara.simulator.backends.base import QSDCBackend
from qsdc.protocols.srikara.simulator.protocol import simulate_qsdc


def run_benchmark(
    config: BenchmarkConfig,
    output_dir: str | None = None,
    write_artifacts: bool = True,
    progress: bool = False,
    progress_stream: TextIO | None = None,
    backend: QSDCBackend | None = None,
) -> BenchmarkRun:
    effective_config = config.with_output_dir(output_dir or config.output_dir)
    base_output_dir = effective_config.output_dir or str(
        Path("results") / "srikara" / "benchmark" / effective_config.name
    )
    effective_config = effective_config.with_output_dir(base_output_dir)
    run_id = f"run_{int(time())}"
    run_dir = str(Path(base_output_dir) / run_id)
    started_at = time()
    combos = _expand_combos(effective_config)
    trials: list[BenchmarkTrial] = []
    completed_combos: list[BenchmarkCombo] = []
    progress_output = progress_stream or sys.stderr
    total_trials = len(combos) * effective_config.trials_per_combo
    completed_trials = 0

    for combo in combos:
        combo_trials = []
        for trial_index in range(effective_config.trials_per_combo):
            trial = _run_trial(effective_config, combo, trial_index, backend)
            trials.append(trial)
            combo_trials.append(trial)

            if progress:
                completed_trials += 1
                fraction = completed_trials / total_trials
                filled = round(24 * fraction)
                bar = "#" * filled + "-" * (24 - filled)
                progress_output.write(
                    f"\r[{bar}] {completed_trials}/{total_trials} trials "
                    f"({fraction:5.1%}), combo {combo.index + 1}/{len(combos)}"
                )
                progress_output.flush()

        completed_combos.append(
            BenchmarkCombo(
                index=combo.index,
                intervals=combo.intervals,
                one_probability=combo.one_probability,
                r_distribution=combo.r_distribution.summary(),
                error_correction=effective_config.error_correction,
                trials=tuple(combo_trials),
            )
        )

    run = BenchmarkRun.from_results(
        run_id,
        run_dir,
        effective_config,
        tuple(trials),
        tuple(completed_combos),
        time() - started_at,
    )
    if write_artifacts:
        if progress:
            progress_output.write("\nWriting artifacts...\n")
            progress_output.flush()
        run = write_benchmark_artifacts(run)
    if progress:
        progress_output.write("Benchmark run finished.\n")
        progress_output.flush()
    return run


@dataclass(frozen=True)
class BenchmarkCase:
    index: int
    seed_index: int
    intervals: IntervalPolicy
    one_probability: float
    r_distribution: SqueezeConfig


def _expand_combos(config: BenchmarkConfig) -> tuple[BenchmarkCase, ...]:
    combos = []
    for intervals in config.interval_policies:
        for seed_index, (one_probability, r_distribution) in enumerate(
            product(config.one_probabilities, config.r_distributions)
        ):
            combos.append(
                BenchmarkCase(
                    len(combos),
                    seed_index,
                    intervals,
                    one_probability,
                    r_distribution,
                )
            )
    return tuple(combos)


def _run_trial(
    config: BenchmarkConfig,
    combo: BenchmarkCase,
    trial_index: int,
    backend: QSDCBackend | None,
) -> BenchmarkTrial:
    trial_seed = derive_seed(config.base_seed, combo.seed_index, trial_index)
    message_seed = derive_seed(trial_seed, "message")
    simulation_seed = derive_seed(trial_seed, "simulation")
    bits = weighted_random_bits(
        config.payload_bit_count,
        combo.one_probability,
        ClassicalRandomSource(message_seed),
    )
    simulator_config = config.simulator_config(
        intervals=combo.intervals,
        squeeze_r_distribution=combo.r_distribution,
        seed=simulation_seed,
    )
    result = simulate_qsdc(bits, simulator_config, backend)
    return BenchmarkTrial(
        combo_index=combo.index,
        trial_index=trial_index,
        seed=trial_seed,
        expected_payload_bits=bits,
        result=result,
        include_sigma_diagnostics=config.sigma_diagnostics,
    )
