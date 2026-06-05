"""Artifact writers for benchmark reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from srikara.benchmark.plot import write_benchmark_plots
from srikara.benchmark.workbook import write_benchmark_workbook


def write_benchmark_artifacts(report: Any) -> None:
    output_dir = Path(report.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_json(output_dir / "config.json", report.effective_config)
    _write_json(output_dir / "combos.json", report.combos)
    with (output_dir / "trials.jsonl").open("w", encoding="utf-8") as handle:
        for trial in report.trials:
            handle.write(json.dumps(trial, sort_keys=True))
            handle.write("\n")
    write_benchmark_workbook(
        output_dir / "benchmark.xlsx",
        report.summary,
        report.combos,
        report.trials,
    )
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
