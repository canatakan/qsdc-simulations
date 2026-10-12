from __future__ import annotations

import csv
import json
import math
import shutil
from collections import Counter
from dataclasses import fields
from pathlib import Path
from time import time_ns

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from ..config import SimulatorConfig
from ..simulator.encoding import INTERVAL_CODES
from .benchmark import Benchmark, BenchmarkResult, Case, RunResult, Workload
from .catalog import GROUPS, NOISES, STUDY_GROUPS
from .metrics import RunMetrics
from .plots import write_plots

TEMPLATES = Path(__file__).parent / "templates"

TABLE_RATES = (
    "bit_error_rate",
    "raw_bit_error_rate",
    "erasure_rate",
    "delivered_fraction",
    "delivered_bits_per_state",
    "information_per_state",
)

GROUP_ORDER = list(GROUPS)
OTHER = {"title": "Other"}

_templates = Environment(
    loader=FileSystemLoader(TEMPLATES),
    autoescape=True,
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


def parameters(case: Case) -> dict[str, str]:
    simulator, workload = case.simulator, case.workload
    noise = next(
        (name for name, preset in NOISES.items() if preset == simulator.noise), None
    )

    return {
        "Backend": simulator.backend,
        "Random source": simulator.random_source,
        "Alpha variance (SNU)": f"{simulator.alpha_variance_snu:g}",
        "Squeezing r": str(simulator.squeeze_r),
        "Theta / pi": str(simulator.theta_pi),
        "Tolerance (sigma)": f"{simulator.tolerance_sigmas:g}",
        "Intervals": simulator.intervals,
        "Axis policy": simulator.axis_policy,
        "Error correction": simulator.error_correction,
        "Max attempts": str(simulator.max_attempts),
        "Noise": noise or simulator.noise.model_dump_json(exclude_defaults=True),
        "Simulation seed": str(simulator.seed),
        "Payload bits": str(workload.payload_bits),
        "Probability of one": f"{workload.one_probability:g}",
        "Payload seed": str(workload.seed),
    }


def run_labels(benchmark: Benchmark) -> list[str]:
    # A run is labelled by the parameters that vary across the benchmark.
    values = [parameters(case) for case in benchmark.cases]
    varying = [key for key in values[0] if len({value[key] for value in values}) > 1]
    if len({case.series for case in benchmark.cases}) > 1:
        varying = [key for key in varying if key != "Noise"]

    return [
        case.label
        or ", ".join(f"{key}: {value[key]}" for key in varying)
        or case.series
        for case, value in zip(benchmark.cases, values)
    ]


def write_report(result: BenchmarkResult, root: Path) -> Path:
    directory = root / result.benchmark.name / f"run_{time_ns()}"
    _write(result, directory)
    return directory


def rerender(results: Path) -> None:
    result = load_result(results)
    shutil.rmtree(results.parent / "plots", ignore_errors=True)
    _write(result, results.parent)


def load_result(results: Path) -> BenchmarkResult:
    document = json.loads(results.read_text())
    runs = tuple(
        RunResult(
            Case(
                SimulatorConfig.model_validate(run["simulator"]),
                Workload.model_validate(run["workload"]),
                run["series"],
                run["label"],
                tuple(run["at"]),
            ),
            _metrics(run["metrics"]),
            tuple(_metrics(values) for values in run["repetitions"]),
        )
        for run in document["runs"]
    )

    info = document["benchmark"]
    benchmark = Benchmark(
        info["name"], tuple(run.case for run in runs), tuple(info["axes"])
    )

    return BenchmarkResult(benchmark, runs, document["summary"]["simulation_seconds"])


def _write(result: BenchmarkResult, directory: Path) -> None:
    benchmark = result.benchmark
    labels = run_labels(benchmark)

    (directory / "plots").mkdir(parents=True)
    plots = write_plots(result, labels, directory / "plots")

    summary = {
        "runs": len(result.runs),
        "repetitions": len(result.runs[0].repetitions),
        "states": sum(run.metrics.states for run in result.runs),
        "simulation_seconds": sum(run.metrics.seconds for run in result.runs),
    }

    runs = [
        {
            "id": position,
            "series": run.case.series,
            "at": list(run.case.at),
            "label": run.case.label,
            "simulator": run.case.simulator.model_dump(mode="json"),
            "workload": run.case.workload.model_dump(mode="json"),
            "metrics": run.metrics.as_dict(),
            "repetitions": [metrics.as_dict() for metrics in run.repetitions],
        }
        for position, run in enumerate(result.runs, start=1)
    ]

    document = {
        "benchmark": {
            "name": benchmark.name,
            "layout": benchmark.layout,
            "axes": list(benchmark.axes),
        },
        "summary": summary,
        "runs": runs,
    }

    (directory / "results.json").write_text(json.dumps(document, indent=2) + "\n")

    rows = [_csv_row(run, benchmark.axes) for run in runs]
    with (directory / "runs.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(dict.fromkeys(key for row in rows for key in row))
        )
        writer.writeheader()
        writer.writerows(rows)

    values = [parameters(case) for case in benchmark.cases]
    shared = {
        key: value
        for key, value in values[0].items()
        if all(other[key] == value for other in values)
    }

    series = len({case.series for case in benchmark.cases}) > 1

    table = [
        {
            "id": position,
            "condition": label,
            "series": run.case.series,
            "cells": [
                *(_rate(run, rate) for rate in TABLE_RATES),
                str(run.metrics.blocks),
                str(run.metrics.retries),
                _rate(run, "check_failure_rate"),
                str(run.metrics.rejected),
                str(run.metrics.uncorrectable),
                _seconds(run.metrics.seconds),
            ],
        }
        for position, (run, label) in enumerate(zip(result.runs, labels), start=1)
    ]

    matrices = [
        {"id": position, "condition": label, **_symbol_matrix(run)}
        for position, (run, label) in enumerate(zip(result.runs, labels), start=1)
    ]

    shutil.copy(TEMPLATES / "style.css", directory / "style.css")
    html = _templates.get_template("report.html").render(
        title=benchmark.name.replace("_", " ").capitalize(),
        layout=benchmark.layout,
        summary=summary,
        single=result.runs[0].metrics if len(result.runs) == 1 else None,
        seconds=_seconds(summary["simulation_seconds"]),
        plots=plots,
        shared=shared,
        show_series=series,
        table=table,
        matrices=matrices,
    )

    (directory / "report.html").write_text(html)


def write_index(root: Path) -> Path:
    latest: dict[str, tuple[Path, dict]] = {}
    executions: Counter[str] = Counter()

    # The latest run of each study, and how many runs it has.
    for path in sorted(root.rglob("results.json")):
        document = json.loads(path.read_text())
        name = document["benchmark"]["name"]
        executions[name] += 1
        latest[name] = (path.parent / "report.html", document)

    groups: dict[str, dict] = {}
    for name in sorted(latest, key=lambda name: (_study_order(name), name)):
        report, document = latest[name]
        summary = document["summary"]
        group = STUDY_GROUPS.get(name, "other")
        if group not in groups:
            groups[group] = {**GROUPS.get(group, OTHER), "rows": []}

        groups[group]["rows"].append(
            {
                "name": name.replace("_", " ").capitalize(),
                "layout": document["benchmark"]["layout"],
                "href": report.relative_to(root).as_posix(),
                "executions": executions[name],
                "runs": summary["runs"],
                "repetitions": summary["repetitions"],
                "seconds": _seconds(summary["simulation_seconds"]),
            }
        )

    root.mkdir(parents=True, exist_ok=True)
    shutil.copy(TEMPLATES / "style.css", root / "style.css")

    index = root / "index.html"
    index.write_text(
        _templates.get_template("index.html").render(
            title=root.name.replace("_", " ").capitalize(), groups=groups
        )
    )

    return index


def _symbol_matrix(run: RunResult) -> dict[str, object]:
    metrics = run.metrics
    labels = INTERVAL_CODES[run.case.simulator.intervals].labels
    counts = [
        [metrics.symbol_counts[8 * int(s, 2) + int(d, 2)] for d in labels]
        for s in labels
    ]

    # Each row shares out the decodings of one sent symbol.
    rows = []
    for label, row in zip(labels, counts):
        total = sum(row) or 1
        cells = [{"count": count, "share": count / total} for count in row]
        rows.append({"label": label, "cells": cells})

    correct = sum(counts[i][i] for i in range(8)) / sum(map(sum, counts))

    return {
        "labels": labels,
        "rows": rows,
        "correct": f"{correct:.1%}",
        "information": f"{metrics.information_per_symbol:.3f}",
    }


def _metrics(values: dict) -> RunMetrics:
    counts = {field.name: values[field.name] for field in fields(RunMetrics)}
    return RunMetrics(**{**counts, "symbol_counts": tuple(counts["symbol_counts"])})


def _csv_row(run: dict, axes: tuple[str, ...]) -> dict[str, object]:
    metrics = dict(run["metrics"])
    counts = metrics.pop("symbol_counts")
    symbols = {
        f"{s:03b}->{d:03b}": counts[8 * s + d] for s in range(8) for d in range(8)
    }

    fields = {k: v for k, v in run.items() if k not in ("at", "metrics", "repetitions")}
    coordinates = dict(zip(axes, run["at"]))

    return _flatten({**fields, **coordinates, "metrics": metrics, "symbols": symbols})


def _flatten(record: dict, prefix: str = "") -> dict[str, object]:
    flat: dict[str, object] = {}
    for key, value in record.items():
        if isinstance(value, dict):
            flat.update(_flatten(value, f"{prefix}{key}."))
        else:
            flat[prefix + key] = value

    return flat


def _study_order(name: str) -> tuple[int, int]:
    group = STUDY_GROUPS.get(name)
    studies = list(STUDY_GROUPS)

    return (
        GROUP_ORDER.index(group) if group in GROUP_ORDER else len(GROUP_ORDER),
        studies.index(name) if name in studies else len(studies),
    )


def _rate(run: RunResult, rate: str) -> str:
    value = getattr(run.metrics, rate)
    if value is None:
        return "—"

    text = "{:.4f}" if rate.endswith("per_state") else "{:.2%}"
    interval = run.interval(rate)
    if math.isnan(interval):
        return text.format(value)

    return f"{text.format(value)} ± {text.format(interval)}"


def _seconds(seconds: float) -> str:
    return f"{seconds * 1000:.1f} ms" if seconds < 1 else f"{seconds:.2f} s"
