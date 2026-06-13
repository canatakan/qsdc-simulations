"""Artifact writers for benchmark reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from qsdc.protocols.srikara.benchmark.artifacts.plots import write_benchmark_plots
from qsdc.protocols.srikara.benchmark.artifacts.report import (
    write_benchmark_html_report,
)
from qsdc.protocols.srikara.benchmark.artifacts.tables import (
    write_combo_csv,
    write_trial_csv,
)


def write_benchmark_artifacts(report: Any) -> None:
    output_dir = Path(report.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    write_combo_csv(output_dir / "combos.csv", report.combos)
    write_trial_csv(output_dir / "trials.csv", report.trials)
    report.summary["artifacts"]["plots"] = write_benchmark_plots(
        output_dir,
        report.combos,
        report.trials,
    )
    report.summary["artifacts"]["html_report"] = write_benchmark_html_report(
        output_dir,
        report.summary,
        report.combos,
        report.trials,
    )
    report.summary["artifacts"]["html_report_css"] = "report.css"
    _write_json(output_dir / "benchmark.json", report.summary)


def _write_json(path: Path, payload: object) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
