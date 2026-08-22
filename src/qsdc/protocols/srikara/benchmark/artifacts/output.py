"""Build and write benchmark artifacts from simulator results."""

from __future__ import annotations

import csv
import json
from collections.abc import Sequence
from dataclasses import asdict, fields, replace
from pathlib import Path

from pydantic import TypeAdapter

from qsdc.protocols.srikara.benchmark.artifacts.metrics import (
    ArtifactTables,
    BenchmarkArtifact,
    BenchmarkRun,
)
from qsdc.protocols.srikara.benchmark.artifacts.plots import write_benchmark_plots
from qsdc.protocols.srikara.benchmark.artifacts.ui import copy_asset, render_template
from qsdc.protocols.srikara.benchmark.artifacts.ui.utils.formatting import (
    human_header,
    table_cell,
)


def write_benchmark_artifacts(run: BenchmarkRun) -> BenchmarkRun:
    output_dir = Path(run.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tables = ArtifactTables.from_results(run.combos, run.trials)
    _write_csv(output_dir / "combos.csv", tables.combos)
    _write_csv(output_dir / "trials.csv", tables.trials)
    _write_csv(output_dir / "decoding.csv", tables.decoding)
    _write_csv(output_dir / "checks.csv", tables.checks)
    _write_csv(output_dir / "corrections.csv", tables.corrections)

    combo_rows = tables.combo_plot_rows()

    trial_rows = [asdict(row) for row in tables.trials]
    if tables.check_sigma_deviations:
        trial_rows.append({"check_sigma_deviations": tables.check_sigma_deviations})

    plots = tuple(write_benchmark_plots(output_dir, combo_rows, trial_rows))
    completed = replace(
        run,
        artifacts=replace(run.artifacts, plots=plots),
    )

    artifact = completed.artifact
    artifact_data = TypeAdapter(BenchmarkArtifact).dump_python(
        artifact, mode="json", exclude_none=True
    )

    _write_html(output_dir, artifact, tables)
    (output_dir / "benchmark.json").write_text(
        json.dumps(artifact_data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return completed


def _write_csv(path: Path, records: Sequence[object]) -> None:
    if not records:
        raise ValueError("cannot write a benchmark table without records")

    fieldnames = tuple(item.name for item in fields(records[0]))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(asdict(record) for record in records)


def _write_html(
    output_dir: Path,
    artifact: BenchmarkArtifact,
    tables: ArtifactTables,
) -> None:
    copy_asset("report.css", output_dir / "report.css")
    (output_dir / "report.html").write_text(
        render_template(
            "report.html",
            artifact=artifact,
            combo_outcomes=_table(tables.combos),
            check_failures=_table(tables.checks),
            artifact_tables=(
                ("combos.csv", _table(tables.combos)),
                ("trials.csv", _table(tables.trials)),
                ("decoding.csv", _table(tables.decoding)),
                ("checks.csv", _table(tables.checks)),
                ("corrections.csv", _table(tables.corrections)),
            ),
        ),
        encoding="utf-8",
    )


def _table(records: Sequence[object]) -> dict[str, object]:
    record_fields = fields(records[0]) if records else ()
    return {
        "headers": [human_header(field.name) for field in record_fields],
        "rows": [
            [
                {"text": table_cell(field.name, getattr(record, field.name))}
                for field in record_fields
            ]
            for record in records
        ],
    }
