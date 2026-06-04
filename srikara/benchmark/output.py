"""Artifact writers for benchmark reports."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def write_benchmark_artifacts(report: Any) -> None:
    output_dir = Path(report.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_json(output_dir / "config.json", report.effective_config)
    _write_json(output_dir / "combos.json", report.combos)
    _write_json(output_dir / "benchmark.json", report.summary)
    with (output_dir / "trials.jsonl").open("w", encoding="utf-8") as handle:
        for trial in report.trials:
            handle.write(json.dumps(trial, sort_keys=True))
            handle.write("\n")
    _write_combos_csv(output_dir / "combos.csv", report.combos)


def _write_json(path: Path, payload: object) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _write_combos_csv(path: Path, combos: list[dict[str, Any]]) -> None:
    columns = [
        "combo_index",
        "one_probability",
        "tolerance",
        "r_distribution",
        "trial_count",
        "accepted_count",
        "accepted_rate",
        "control_pass_rate",
        "decoy_pass_rate",
        "all_bit_error_rate",
        "accepted_bit_error_rate",
        "rejected_bit_error_rate",
        "all_symbol_error_rate",
        "accepted_symbol_error_rate",
        "rejected_symbol_error_rate",
        "all_mean_abs_value_error",
        "all_mean_interval_margin",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for combo in combos:
            row = {
                "combo_index": combo["combo_index"],
                "one_probability": combo["one_probability"],
                "tolerance": combo["tolerance"],
                "r_distribution": combo["r_distribution"],
                "trial_count": combo["trial_count"],
                "accepted_count": combo["accepted_count"],
                "accepted_rate": combo["accepted_rate"],
                "control_pass_rate": combo["control_pass_rate"],
                "decoy_pass_rate": combo["decoy_pass_rate"],
                "all_bit_error_rate": combo["all"]["bit_error_rate"],
                "accepted_bit_error_rate": combo["accepted"]["bit_error_rate"],
                "rejected_bit_error_rate": combo["rejected"]["bit_error_rate"],
                "all_symbol_error_rate": combo["all"]["symbol_error_rate"],
                "accepted_symbol_error_rate": combo["accepted"]["symbol_error_rate"],
                "rejected_symbol_error_rate": combo["rejected"]["symbol_error_rate"],
                "all_mean_abs_value_error": combo["all"]["mean_abs_value_error"],
                "all_mean_interval_margin": combo["all"]["mean_interval_margin"],
            }
            writer.writerow(row)
