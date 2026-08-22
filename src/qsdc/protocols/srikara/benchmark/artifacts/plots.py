"""Matplotlib plot generation for benchmark artifacts."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from math import ceil
from pathlib import Path
from statistics import mean
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pydantic import TypeAdapter

from qsdc.protocols.srikara.benchmark.artifacts.metrics import (
    ArtifactTables,
    BenchmarkArtifact,
)

Combo = dict[str, Any]
Trial = dict[str, Any]


@dataclass(frozen=True)
class ErrorPlotSpec:
    filename: str
    title: str
    y_label: str
    metric_field: str


ERROR_PLOT_SPECS: tuple[ErrorPlotSpec, ...] = (
    ErrorPlotSpec(
        filename="raw_bit_error_by_r.png",
        title="Raw Modulation-Bit Error by r Distribution",
        y_label="raw measured bit error rate",
        metric_field="raw_bit_error_rate",
    ),
    ErrorPlotSpec(
        filename="raw_symbol_error_by_r.png",
        title="Raw 3-Bit Symbol Error by r Distribution",
        y_label="raw measured symbol error rate",
        metric_field="raw_symbol_error_rate",
    ),
    ErrorPlotSpec(
        filename="value_error_by_r.png",
        title="Mean Absolute Numeric Recovery Error by r Distribution",
        y_label="mean |decoded - sampled|",
        metric_field="mean_abs_value_error",
    ),
)

RECOVERED_PAYLOAD_PLOT_SPEC = ErrorPlotSpec(
    filename="recovered_payload_bit_error_by_r.png",
    title="Recovered Payload Bit Error by r Distribution",
    y_label="recovered payload bit error rate",
    metric_field="recovered_payload_bit_error_rate",
)

DEFAULT_INTERVAL_LABEL = "default"
SIGMA_DIAGNOSTIC_CURVE_FILENAME = "check_sigma_pass_curve.png"
MAX_SIGMA_CURVE_POINTS = 800
INTERVAL_COLORS = {
    "default": "#d8d8d8",
    "optimized_v4": "#fc8d59",
    "optimized_v8": "#91bfdb",
    "optimized_v12": "#998ec3",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", help="benchmark run directory")
    args = parser.parse_args()

    plots = write_plots_from_artifacts(args.output_dir)
    print(f"Generated {len(plots)} plot(s) in {Path(args.output_dir) / 'plots'}")


def write_plots_from_artifacts(output_dir: str | Path) -> list[str]:
    output_path = Path(output_dir)
    tables = ArtifactTables.read(output_path)
    combos = tables.combo_plot_rows()
    trials = [asdict(row) for row in tables.trials]
    plots = write_benchmark_plots(output_path, combos, trials)
    benchmark_path = output_path / "benchmark.json"
    if benchmark_path.exists():
        artifact = TypeAdapter(BenchmarkArtifact).validate_json(
            benchmark_path.read_text(encoding="utf-8")
        )
        artifact = replace(
            artifact,
            artifacts=replace(artifact.artifacts, plots=tuple(plots)),
        )
        benchmark_path.write_text(
            json.dumps(
                TypeAdapter(BenchmarkArtifact).dump_python(artifact, mode="json"),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    return plots


def write_benchmark_plots(
    output_dir: str | Path,
    combos: list[Combo],
    trials: list[Trial] | None = None,
) -> list[str]:
    plots_dir = Path(output_dir) / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    plots: list[str] = []
    specs = list(ERROR_PLOT_SPECS)
    if any(str(combo.get("error_correction")) == "secded" for combo in combos):
        specs.append(RECOVERED_PAYLOAD_PLOT_SPEC)
    for spec in specs:
        interval_path = plots_dir / f"{Path(spec.filename).stem}_by_interval.png"
        _write_interval_metric_plot(interval_path, combos, spec)
        plots.append(str(Path("plots") / interval_path.name))

        delta_path = plots_dir / f"{Path(spec.filename).stem}_delta_vs_default.png"
        if _write_interval_delta_plot(delta_path, combos, spec):
            plots.append(str(Path("plots") / delta_path.name))

    sigma_deviations = _all_check_sigma_deviations(trials or [])
    if sigma_deviations:
        sigma_path = plots_dir / SIGMA_DIAGNOSTIC_CURVE_FILENAME
        _write_sigma_diagnostic_curve(sigma_path, sigma_deviations)
        plots.append(str(Path("plots") / sigma_path.name))

    return plots


def _write_interval_metric_plot(
    path: Path,
    combos: list[Combo],
    spec: ErrorPlotSpec,
) -> None:
    r_labels = _unique_sorted(str(combo["r_distribution"]) for combo in combos)
    probabilities = _unique_sorted(float(combo["one_probability"]) for combo in combos)
    intervals = _unique_ordered(str(combo["intervals"]) for combo in combos)
    values = _combo_metric_table(combos, spec.metric_field)

    figure, axes = _probability_axes(probabilities)
    positions = list(range(len(r_labels)))
    bar_width = 0.8 / max(len(intervals), 1)
    for axis, probability in zip(axes, probabilities):
        for interval_index, intervals_label in enumerate(intervals):
            offset = (interval_index - (len(intervals) - 1) / 2) * bar_width
            x_values = [position + offset for position in positions]
            y_values = [
                values.get((intervals_label, probability, r_label), 0.0)
                for r_label in r_labels
            ]
            axis.bar(
                x_values,
                y_values,
                width=bar_width,
                color=_interval_color(intervals_label),
                label=intervals_label,
            )
        _style_metric_axis(axis, r_labels, f"p={probability:g}", spec.y_label)

    _hide_unused_axes(axes, len(probabilities))
    figure.suptitle(
        f"{spec.title} by Interval Policy",
        fontweight="bold",
        y=1.18,
    )
    _legend_for_intervals(figure, axes[0], intervals)
    figure.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(figure)


def _combo_metric_table(
    combos: list[Combo],
    metric_field: str,
) -> dict[tuple[str, float, str], float]:
    values: dict[tuple[str, float, str], float] = {}
    for combo in combos:
        y_value = combo.get(metric_field)
        if y_value in ("", None):
            continue
        values[
            (
                str(combo["intervals"]),
                float(combo["one_probability"]),
                str(combo["r_distribution"]),
            )
        ] = float(y_value)
    return values


def _write_interval_delta_plot(
    path: Path,
    combos: list[Combo],
    spec: ErrorPlotSpec,
) -> bool:
    r_labels = _unique_sorted(str(combo["r_distribution"]) for combo in combos)
    probabilities = _unique_sorted(float(combo["one_probability"]) for combo in combos)
    intervals = [
        intervals_label
        for intervals_label in _unique_ordered(
            str(combo["intervals"]) for combo in combos
        )
        if intervals_label != DEFAULT_INTERVAL_LABEL
    ]
    if not intervals:
        return False
    values = _combo_metric_table(combos, spec.metric_field)
    if not any(
        (DEFAULT_INTERVAL_LABEL, probability, r_label) in values
        for probability in probabilities
        for r_label in r_labels
    ):
        return False

    figure, axes = _probability_axes(probabilities)
    positions = list(range(len(r_labels)))
    bar_width = 0.8 / max(len(intervals), 1)
    for axis, probability in zip(axes, probabilities):
        for interval_index, intervals_label in enumerate(intervals):
            offset = (interval_index - (len(intervals) - 1) / 2) * bar_width
            x_values = [position + offset for position in positions]
            y_values = []
            for r_label in r_labels:
                baseline = values.get((DEFAULT_INTERVAL_LABEL, probability, r_label))
                candidate = values.get((intervals_label, probability, r_label))
                y_values.append(
                    0.0
                    if baseline is None or candidate is None
                    else baseline - candidate
                )
            axis.bar(
                x_values,
                y_values,
                width=bar_width,
                color=_interval_color(intervals_label),
                label=intervals_label,
            )
        axis.axhline(0.0, color="#172033", linewidth=0.8)
        _style_metric_axis(
            axis,
            r_labels,
            f"p={probability:g}",
            f"default - {spec.y_label}",
        )

    _hide_unused_axes(axes, len(probabilities))
    figure.suptitle(
        f"{spec.title}: Improvement vs Default",
        fontweight="bold",
        y=1.18,
    )
    _legend_for_intervals(figure, axes[0], intervals)
    figure.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(figure)
    return True


def _write_sigma_diagnostic_curve(path: Path, thresholds: list[float]) -> None:
    x_values, y_values = _pass_curve(thresholds)
    figure, axis = plt.subplots(figsize=(7.2, 4.6), constrained_layout=True)
    axis.step(
        x_values,
        y_values,
        where="post",
        linewidth=2.4,
        color="#3f6f9f",
    )
    if thresholds:
        mean_value = mean(thresholds)
        mean_fraction = _accepted_fraction(thresholds, mean_value)
        axis.axvline(
            mean_value,
            color="#1f2937",
            linestyle=":",
            linewidth=1.4,
        )
        axis.scatter(
            [mean_value],
            [mean_fraction],
            color="#1f2937",
            s=28,
            zorder=3,
        )
        axis.annotate(
            f"mean = {mean_value:.3g}",
            xy=(mean_value, mean_fraction),
            xytext=(8, -14),
            textcoords="offset points",
            fontsize=9,
            color="#1f2937",
        )

    axis.set_title("Check Passing Fraction by Sigma Deviation", fontweight="bold")
    axis.set_xlabel("candidate sigma deviation")
    axis.set_ylabel("fraction of all checks passing")
    axis.set_ylim(0.0, 1.0)
    axis.grid(True, alpha=0.3)
    figure.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(figure)


def _all_check_sigma_deviations(trials: list[Trial]) -> list[float]:
    values: list[float] = []
    for trial in trials:
        check_values = trial.get("check_sigma_deviations")
        if isinstance(check_values, (list, tuple)):
            values.extend(float(value) for value in check_values)
    return values


def _pass_curve(thresholds: list[float]) -> tuple[list[float], list[float]]:
    if not thresholds:
        return [0.0], [0.0]

    sorted_thresholds = sorted(thresholds)
    x_values = [0.0]
    y_values = [0.0]
    index = 0
    total = len(sorted_thresholds)
    while index < total:
        candidate = sorted_thresholds[index]
        while index < total and sorted_thresholds[index] == candidate:
            index += 1
        x_values.append(candidate)
        y_values.append(index / total)

    return _plot_curve_points(x_values, y_values)


def _plot_curve_points(
    x_values: list[float],
    y_values: list[float],
) -> tuple[list[float], list[float]]:
    if len(x_values) <= MAX_SIGMA_CURVE_POINTS:
        return x_values, y_values

    last_index = len(x_values) - 1
    indices = [
        round(point * last_index / (MAX_SIGMA_CURVE_POINTS - 1))
        for point in range(MAX_SIGMA_CURVE_POINTS)
    ]
    return (
        [x_values[index] for index in indices],
        [y_values[index] for index in indices],
    )


def _accepted_fraction(thresholds: list[float], candidate: float) -> float:
    return sum(threshold <= candidate for threshold in thresholds) / len(thresholds)


def _unique_sorted(values) -> list:
    return sorted(set(values))


def _unique_ordered(values) -> list:
    ordered = []
    for value in values:
        if value not in ordered:
            ordered.append(value)
    return ordered


def _probability_axes(probabilities: Sequence[float]):
    column_count = min(3, max(len(probabilities), 1))
    row_count = ceil(max(len(probabilities), 1) / column_count)
    return _subplots(row_count, column_count)


def _subplots(row_count: int, column_count: int):
    figure, axes = plt.subplots(
        row_count,
        column_count,
        figsize=(5.2 * column_count, 4.2 * row_count),
        constrained_layout=True,
        squeeze=False,
    )
    return figure, [axis for row in axes for axis in row]


def _style_metric_axis(axis, r_labels: list[str], title: str, y_label: str) -> None:
    axis.set_title(title)
    axis.set_xlabel("r distribution")
    axis.set_ylabel(y_label)
    axis.set_xticks(list(range(len(r_labels))))
    axis.set_xticklabels(r_labels, rotation=25, ha="right")
    axis.grid(True, axis="y", alpha=0.3)


def _legend_for_intervals(figure, axis, intervals: Sequence[str]) -> None:
    handles, labels = axis.get_legend_handles_labels()
    by_label = {
        label: handle for handle, label in zip(handles, labels) if label in intervals
    }
    figure.legend(
        by_label.values(),
        by_label.keys(),
        loc="upper center",
        bbox_to_anchor=(0.5, 1.09),
        ncol=max(1, min(4, len(by_label))),
        frameon=False,
    )


def _hide_unused_axes(axes, used_count: int) -> None:
    for axis in axes[used_count:]:
        axis.set_visible(False)


def _interval_color(intervals_label: str) -> str:
    if intervals_label in INTERVAL_COLORS:
        return INTERVAL_COLORS[intervals_label]
    colormap = plt.get_cmap("tab20")
    return colormap(abs(hash(intervals_label)) % 20)


if __name__ == "__main__":
    main()
