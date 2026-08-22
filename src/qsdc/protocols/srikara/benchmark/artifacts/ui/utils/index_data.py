"""Load and aggregate benchmark runs for the multi-run index."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from pydantic import TypeAdapter

from qsdc.protocols.srikara.benchmark.artifacts.metrics import (
    ArtifactTables,
    BenchmarkArtifact,
)

Run = dict[str, Any]
Combo = dict[str, Any]


def find_runs(root: Path) -> list[Run]:
    runs = []
    for benchmark_path in sorted(root.rglob("benchmark.json")):
        run_dir = benchmark_path.parent
        artifact = TypeAdapter(BenchmarkArtifact).validate_json(
            benchmark_path.read_text(encoding="utf-8")
        )
        combos = []
        if (run_dir / "combos.csv").exists():
            combos = ArtifactTables.read(run_dir).combo_plot_rows()
        runs.append(_run_row(root, run_dir, artifact, combos))
    return sorted(runs, key=_run_sort_key)


def group_runs(runs: list[Run]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Run]] = {}
    for run in runs:
        grouped.setdefault(str(run["name"]), []).append(run)

    groups = []
    for name, group_items in grouped.items():
        ordered_runs = sorted(group_items, key=lambda run: run["run_order"])
        groups.append({"name": name, "runs": ordered_runs, "latest": ordered_runs[-1]})
    return sorted(groups, key=lambda group: str(group["name"]))


def group_families(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for group in groups:
        family, _ = split_group_name(str(group["name"]))
        grouped.setdefault(family, []).append(group)
    return [
        {
            "name": family,
            "report_groups": report_groups,
            "run_count": sum(len(group["runs"]) for group in report_groups),
        }
        for family, report_groups in sorted(grouped.items())
    ]


def split_group_name(name: str) -> tuple[str, str]:
    if "/" not in name:
        return name, name
    return tuple(name.split("/", 1))


def non_quick_runs(runs: list[Run]) -> list[Run]:
    return [run for run in runs if not str(run["name"]).startswith("quick/")]


def delta_from_default(
    row: dict[str, Any],
    rows: list[dict[str, Any]],
    field: str,
) -> float | None:
    default_row = next(
        (candidate for candidate in rows if candidate.get("intervals") == "default"),
        None,
    )
    if default_row is None or default_row.get(field) is None or row.get(field) is None:
        return None
    return float(default_row[field]) - float(row[field])


def best_run_value(runs: list[Run], row_key: str, field: str) -> float | None:
    values = [
        float(run[row_key][field])
        for run in runs
        if run.get(row_key) is not None and run[row_key].get(field) is not None
    ]
    return min(values) if values else None


def _run_row(
    root: Path,
    run_dir: Path,
    artifact: BenchmarkArtifact,
    combos: list[Combo],
) -> Run:
    config = artifact.config
    metrics = artifact.metrics
    report_path = run_dir / artifact.artifacts.html_report
    balanced_combos = _balanced_combos(combos)
    _, report_name = split_group_name(config.name)
    return {
        "name": config.name,
        "report_name": report_name,
        "run_id": artifact.run_id,
        "run_order": _run_order(artifact.run_id),
        "backend": config.backend,
        "interval_policies": config.interval_policies,
        "check_axis_policy": config.check_axis_policy,
        "message_axis_policy": config.message_axis_policy,
        "alpha_distribution": config.alpha_distribution.summary(),
        "theta_distribution": config.theta_distribution.summary(),
        "one_probabilities": _unique_sorted(
            float(combo["one_probability"])
            for combo in combos
            if combo.get("one_probability") not in ("", None)
        ),
        "interval_rows": _interval_rows(combos),
        "best_mean_bit": _best_row(
            _interval_rows(balanced_combos), "raw_bit_error_rate", min
        ),
        "best_mean_symbol": _best_row(
            _interval_rows(balanced_combos), "raw_symbol_error_rate", min
        ),
        "best_combo_bit": _best_row(balanced_combos, "raw_bit_error_rate", min),
        "best_combo_symbol": _best_row(balanced_combos, "raw_symbol_error_rate", min),
        "accepted_rate": metrics.protocol_acceptance_rate,
        "trial_count": metrics.trial_count,
        "mean_bit_error_rate": _weighted_average(
            balanced_combos,
            "raw_bit_error_rate",
        ),
        "mean_symbol_error_rate": _weighted_average(
            balanced_combos, "raw_symbol_error_rate"
        ),
        "report_href": report_path.relative_to(root),
    }


def _run_sort_key(run: Run) -> tuple[str, ...]:
    return (
        str(run["name"]),
        str(run["interval_policies"]),
        str(run["check_axis_policy"]),
        str(run["message_axis_policy"]),
        str(run["alpha_distribution"]),
        str(run["theta_distribution"]),
        str(run["run_id"]),
    )


def _interval_rows(combos: list[Combo]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Combo]] = {}
    for combo in combos:
        grouped.setdefault(str(combo["intervals"]), []).append(combo)
    return [
        _interval_row(intervals, grouped[intervals])
        for intervals in _unique_ordered(grouped)
    ]


def _interval_row(intervals: str, combos: list[Combo]) -> dict[str, Any]:
    balanced_combos = _balanced_combos(combos)
    return {
        "intervals": intervals,
        "accepted_rate": _weighted_average(combos, "protocol_acceptance_rate"),
        "raw_bit_error_rate": _weighted_average(combos, "raw_bit_error_rate"),
        "raw_symbol_error_rate": _weighted_average(
            combos,
            "raw_symbol_error_rate",
        ),
        "balanced_bit_error_rate": _weighted_average(
            balanced_combos, "raw_bit_error_rate"
        ),
        "balanced_symbol_error_rate": _weighted_average(
            balanced_combos, "raw_symbol_error_rate"
        ),
        "mean_abs_value_error": _weighted_average(combos, "mean_abs_value_error"),
    }


def _weighted_average(combos: list[Combo], field: str) -> float | None:
    weighted_total = 0.0
    total_weight = 0.0
    for combo in combos:
        if combo.get(field) in ("", None):
            continue
        weight = float(combo.get("trial_count") or 1.0)
        weighted_total += float(combo[field]) * weight
        total_weight += weight
    return weighted_total / total_weight if total_weight else None


def _balanced_combos(combos: list[Combo]) -> list[Combo]:
    return [
        combo
        for combo in combos
        if combo.get("one_probability") not in ("", None)
        and float(combo["one_probability"]) == 0.5
    ]


def _best_row(
    rows: list[dict[str, Any]],
    field: str,
    selector: Callable,
) -> dict[str, Any] | None:
    candidates = [row for row in rows if row.get(field) not in ("", None)]
    if not candidates:
        return None
    selected_value = selector(float(row[field]) for row in candidates)
    return next(row for row in candidates if float(row[field]) == selected_value)


def _run_order(value: object) -> int:
    if value is None:
        return 0
    identifier = str(value).removeprefix("run_")
    return int(identifier) if identifier.isdigit() else 0


def _unique_sorted(values) -> list:
    return sorted(set(values))


def _unique_ordered(values) -> list:
    return list(dict.fromkeys(values))
