"""Artifact writers for benchmark reports."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from srikara.benchmark.plot import write_benchmark_plots


def write_benchmark_artifacts(report: Any) -> None:
    output_dir = Path(report.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_json(output_dir / "config.json", report.effective_config)
    _write_json(output_dir / "combos.json", report.combos)
    with (output_dir / "trials.jsonl").open("w", encoding="utf-8") as handle:
        for trial in report.trials:
            handle.write(json.dumps(trial, sort_keys=True))
            handle.write("\n")
    _write_combos_csv(output_dir / "combos.csv", report.combos)
    report.summary["artifacts"]["plots"] = write_benchmark_plots(
        output_dir,
        report.combos,
        report.trials,
    )
    _write_json(output_dir / "benchmark.json", report.summary)


def _write_json(path: Path, payload: object) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _write_combos_csv(path: Path, combos: list[dict[str, Any]]) -> None:
    columns = [
        "combo_index",
        "one_probability",
        "r_distribution",
        "trial_count",
        "accepted_count",
        "accepted_rate",
        "control_pass_rate",
        "decoy_pass_rate",
        "check_tolerance_sigmas",
        "measurement_noise_sigma",
        "control_check_count",
        "control_failed_check_count",
        "control_failed_check_rate",
        "control_mean_failed_check_count_per_trial",
        "control_max_failed_check_count_per_trial",
        "decoy_check_count",
        "decoy_failed_check_count",
        "decoy_failed_check_rate",
        "decoy_mean_failed_check_count_per_trial",
        "decoy_max_failed_check_count_per_trial",
        "all_bit_error_rate",
        "accepted_bit_error_rate",
        "rejected_bit_error_rate",
        "all_symbol_error_rate",
        "accepted_symbol_error_rate",
        "rejected_symbol_error_rate",
        "all_mean_abs_value_error",
        "all_mean_interval_margin",
        "all_required_acceptance_tolerance_sigmas_min",
        "all_required_acceptance_tolerance_sigmas_mean",
        "all_required_acceptance_tolerance_sigmas_median",
        "all_required_acceptance_tolerance_sigmas_p95",
        "all_required_acceptance_tolerance_sigmas_max",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for combo in combos:
            row = {
                "combo_index": combo["combo_index"],
                "one_probability": combo["one_probability"],
                "r_distribution": combo["r_distribution"],
                "trial_count": combo["trial_count"],
                "accepted_count": combo["accepted_count"],
                "accepted_rate": combo["accepted_rate"],
                "control_pass_rate": combo["control_pass_rate"],
                "decoy_pass_rate": combo["decoy_pass_rate"],
                "check_tolerance_sigmas": combo["check_tolerance_sigmas"],
                "measurement_noise_sigma": combo["measurement_noise_sigma"],
                "control_check_count": combo["control_check_count"],
                "control_failed_check_count": combo["control_failed_check_count"],
                "control_failed_check_rate": combo["control_failed_check_rate"],
                "control_mean_failed_check_count_per_trial": (
                    combo["control_mean_failed_check_count_per_trial"]
                ),
                "control_max_failed_check_count_per_trial": (
                    combo["control_max_failed_check_count_per_trial"]
                ),
                "decoy_check_count": combo["decoy_check_count"],
                "decoy_failed_check_count": combo["decoy_failed_check_count"],
                "decoy_failed_check_rate": combo["decoy_failed_check_rate"],
                "decoy_mean_failed_check_count_per_trial": (
                    combo["decoy_mean_failed_check_count_per_trial"]
                ),
                "decoy_max_failed_check_count_per_trial": (
                    combo["decoy_max_failed_check_count_per_trial"]
                ),
                "all_bit_error_rate": combo["all"]["bit_error_rate"],
                "accepted_bit_error_rate": combo["accepted"]["bit_error_rate"],
                "rejected_bit_error_rate": combo["rejected"]["bit_error_rate"],
                "all_symbol_error_rate": combo["all"]["symbol_error_rate"],
                "accepted_symbol_error_rate": combo["accepted"]["symbol_error_rate"],
                "rejected_symbol_error_rate": combo["rejected"]["symbol_error_rate"],
                "all_mean_abs_value_error": combo["all"]["mean_abs_value_error"],
                "all_mean_interval_margin": combo["all"]["mean_interval_margin"],
                "all_required_acceptance_tolerance_sigmas_min": (
                    combo["all"]["required_acceptance_tolerance_sigmas"]["min"]
                ),
                "all_required_acceptance_tolerance_sigmas_mean": (
                    combo["all"]["required_acceptance_tolerance_sigmas"]["mean"]
                ),
                "all_required_acceptance_tolerance_sigmas_median": (
                    combo["all"]["required_acceptance_tolerance_sigmas"]["median"]
                ),
                "all_required_acceptance_tolerance_sigmas_p95": (
                    combo["all"]["required_acceptance_tolerance_sigmas"]["p95"]
                ),
                "all_required_acceptance_tolerance_sigmas_max": (
                    combo["all"]["required_acceptance_tolerance_sigmas"]["max"]
                ),
            }
            writer.writerow(row)
