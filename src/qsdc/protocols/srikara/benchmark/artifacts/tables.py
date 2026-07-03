"""CSV table writers for benchmark artifacts."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


Combo = dict[str, Any]
Trial = dict[str, Any]

COMBO_FIELDS = (
    "combo_index",
    "one_probability",
    "r_distribution",
    "trial_count",
    "accepted_count",
    "accepted_rate",
    "control_pass_rate",
    "decoy_pass_rate",
    "bit_error_rate",
    "symbol_error_rate",
    "mean_abs_value_error",
    "mean_interval_margin",
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
    "required_acceptance_tolerance_sigmas_min",
    "required_acceptance_tolerance_sigmas_median",
    "required_acceptance_tolerance_sigmas_mean",
    "required_acceptance_tolerance_sigmas_p95",
    "required_acceptance_tolerance_sigmas_max",
)

TRIAL_FIELDS = (
    "combo_index",
    "trial_index",
    "trial_seed",
    "check_axis_policy",
    "message_axis_policy",
    "one_probability",
    "r_distribution",
    "accepted",
    "control_passed",
    "decoy_passed",
    "control_failed_check_count",
    "decoy_failed_check_count",
    "required_control_tolerance_sigmas",
    "required_decoy_tolerance_sigmas",
    "required_acceptance_tolerance_sigmas",
    "bit_error_rate",
    "symbol_error_rate",
    "mean_abs_value_error",
    "mean_interval_margin",
)


def write_combo_csv(path: Path, combos: list[Combo]) -> None:
    _write_csv(path, COMBO_FIELDS, combo_csv_rows(combos))


def write_trial_csv(path: Path, trials: list[Trial]) -> None:
    _write_csv(path, TRIAL_FIELDS, trial_csv_rows(trials))


def combo_csv_rows(combos: list[Combo]) -> list[dict[str, object]]:
    return [_combo_row(combo) for combo in combos]


def trial_csv_rows(trials: list[Trial]) -> list[dict[str, object]]:
    return [_trial_row(trial) for trial in trials]


def read_combo_csv(path: Path) -> list[Combo]:
    return _read_csv(path)


def read_trial_csv(path: Path) -> list[Trial]:
    return _read_csv(path)


def _combo_row(combo: Combo) -> dict[str, object]:
    metrics = combo["all"]
    thresholds = metrics["required_acceptance_tolerance_sigmas"]
    return {
        "combo_index": combo["combo_index"],
        "one_probability": combo["one_probability"],
        "r_distribution": combo["r_distribution"],
        "trial_count": combo["trial_count"],
        "accepted_count": combo["accepted_count"],
        "accepted_rate": combo["accepted_rate"],
        "control_pass_rate": combo["control_pass_rate"],
        "decoy_pass_rate": combo["decoy_pass_rate"],
        "bit_error_rate": metrics["bit_error_rate"],
        "symbol_error_rate": metrics["symbol_error_rate"],
        "mean_abs_value_error": metrics["mean_abs_value_error"],
        "mean_interval_margin": metrics["mean_interval_margin"],
        "check_tolerance_sigmas": combo["check_tolerance_sigmas"],
        "measurement_noise_sigma": combo["measurement_noise_sigma"],
        "control_check_count": combo["control_check_count"],
        "control_failed_check_count": combo["control_failed_check_count"],
        "control_failed_check_rate": combo["control_failed_check_rate"],
        "control_mean_failed_check_count_per_trial": combo[
            "control_mean_failed_check_count_per_trial"
        ],
        "control_max_failed_check_count_per_trial": combo[
            "control_max_failed_check_count_per_trial"
        ],
        "decoy_check_count": combo["decoy_check_count"],
        "decoy_failed_check_count": combo["decoy_failed_check_count"],
        "decoy_failed_check_rate": combo["decoy_failed_check_rate"],
        "decoy_mean_failed_check_count_per_trial": combo[
            "decoy_mean_failed_check_count_per_trial"
        ],
        "decoy_max_failed_check_count_per_trial": combo[
            "decoy_max_failed_check_count_per_trial"
        ],
        "required_acceptance_tolerance_sigmas_min": thresholds["min"],
        "required_acceptance_tolerance_sigmas_median": thresholds["median"],
        "required_acceptance_tolerance_sigmas_mean": thresholds["mean"],
        "required_acceptance_tolerance_sigmas_p95": thresholds["p95"],
        "required_acceptance_tolerance_sigmas_max": thresholds["max"],
    }


def _trial_row(trial: Trial) -> dict[str, object]:
    return {
        "combo_index": trial["combo_index"],
        "trial_index": trial["trial_index"],
        "trial_seed": trial["trial_seed"],
        "check_axis_policy": trial["check_axis_policy"],
        "message_axis_policy": trial["message_axis_policy"],
        "one_probability": trial["one_probability"],
        "r_distribution": trial["r_distribution"],
        "accepted": trial["accepted"],
        "control_passed": trial["control_passed"],
        "decoy_passed": trial["decoy_passed"],
        "control_failed_check_count": trial["control_failed_check_count"],
        "decoy_failed_check_count": trial["decoy_failed_check_count"],
        "required_control_tolerance_sigmas": trial[
            "required_control_tolerance_sigmas"
        ],
        "required_decoy_tolerance_sigmas": trial["required_decoy_tolerance_sigmas"],
        "required_acceptance_tolerance_sigmas": trial[
            "required_acceptance_tolerance_sigmas"
        ],
        "bit_error_rate": trial["bit_error_rate"],
        "symbol_error_rate": trial["symbol_error_rate"],
        "mean_abs_value_error": trial["mean_abs_value_error"],
        "mean_interval_margin": trial["mean_interval_margin"],
    }


def _write_csv(
    path: Path,
    fields: tuple[str, ...],
    rows: list[dict[str, object]],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))
