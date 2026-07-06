"""Matplotlib plot generation for benchmark artifacts."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from math import ceil
from pathlib import Path
from typing import Any, Optional, Sequence, Union

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from qsdc.protocols.srikara.benchmark.artifacts.report import (
    write_benchmark_html_report,
)
from qsdc.protocols.srikara.benchmark.artifacts.tables import (
    read_combo_csv,
    read_trial_csv,
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
        filename="bit_error_by_r.png",
        title="Payload Bit Error by r Distribution",
        y_label="bit error rate",
        metric_field="bit_error_rate",
    ),
    ErrorPlotSpec(
        filename="symbol_error_by_r.png",
        title="3-Bit Symbol Error by r Distribution",
        y_label="symbol error rate",
        metric_field="symbol_error_rate",
    ),
    ErrorPlotSpec(
        filename="value_error_by_r.png",
        title="Mean Absolute Numeric Recovery Error by r Distribution",
        y_label="mean |decoded - sampled|",
        metric_field="mean_abs_value_error",
    ),
)

THRESHOLD_CURVE_FILENAME = "derived_acceptance_tolerance_sigmas_curve.png"
DEFAULT_INTERVAL_LABEL = "default"
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
    combos = read_combo_csv(output_path / "combos.csv")
    trials = read_trial_csv(output_path / "trials.csv")
    plots = write_benchmark_plots(output_path, combos, trials)
    benchmark_path = output_path / "benchmark.json"
    if benchmark_path.exists():
        with benchmark_path.open("r", encoding="utf-8") as handle:
            benchmark = json.load(handle)
        benchmark.setdefault("artifacts", {})["plots"] = plots
        benchmark["artifacts"]["html_report"] = write_benchmark_html_report(
            output_path,
            benchmark,
            combos,
            trials,
        )
        benchmark["artifacts"]["html_report_css"] = "report.css"
        with benchmark_path.open("w", encoding="utf-8") as handle:
            json.dump(benchmark, handle, indent=2, sort_keys=True)
            handle.write("\n")
    return plots


def write_benchmark_plots(
    output_dir: str | Path,
    combos: list[Combo],
    trials: list[Trial],
) -> list[str]:
    plots_dir = Path(output_dir) / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    plots: list[str] = []
    for spec in ERROR_PLOT_SPECS:
        interval_path = plots_dir / _interval_metric_filename(spec.filename)
        _write_interval_metric_plot(interval_path, combos, spec)
        plots.append(str(Path("plots") / interval_path.name))

        delta_path = plots_dir / _delta_metric_filename(spec.filename)
        if _write_interval_delta_plot(delta_path, combos, spec):
            plots.append(str(Path("plots") / delta_path.name))

    threshold_path = plots_dir / THRESHOLD_CURVE_FILENAME
    _write_threshold_curve(threshold_path, trials)
    plots.append(str(Path("plots") / THRESHOLD_CURVE_FILENAME))
    return plots


def _interval_metric_filename(filename: str) -> str:
    stem = Path(filename).stem
    return f"{stem}_by_interval.png"


def _delta_metric_filename(filename: str) -> str:
    stem = Path(filename).stem
    return f"{stem}_delta_vs_default.png"


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
        y_value = _combo_metric(combo, metric_field)
        if y_value is None:
            continue
        values[
            (
                str(combo["intervals"]),
                float(combo["one_probability"]),
                str(combo["r_distribution"]),
            )
        ] = float(y_value)
    return values


def _combo_metric(
    combo: Combo,
    metric_field: str,
) -> Optional[Union[float, int]]:
    if metric_field in combo:
        return float(combo[metric_field])
    if "all" in combo and metric_field in combo["all"]:
        return float(combo["all"][metric_field])
    return None


def _write_interval_delta_plot(
    path: Path,
    combos: list[Combo],
    spec: ErrorPlotSpec,
) -> bool:
    r_labels = _unique_sorted(str(combo["r_distribution"]) for combo in combos)
    probabilities = _unique_sorted(float(combo["one_probability"]) for combo in combos)
    intervals = [
        intervals_label
        for intervals_label in _unique_ordered(str(combo["intervals"]) for combo in combos)
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
                    0.0 if baseline is None or candidate is None else baseline - candidate
                )
            axis.bar(
                x_values,
                y_values,
                width=bar_width,
                color=_interval_color(intervals_label),
                label=intervals_label,
            )
        axis.axhline(0.0, color="#172033", linewidth=0.8)
        _style_metric_axis(axis, r_labels, f"p={probability:g}", f"default - {spec.y_label}")

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


def _write_threshold_curve(path: Path, trials: list[Trial]) -> None:
    intervals = _unique_ordered(str(trial["intervals"]) for trial in trials)
    series_by_interval = _threshold_series_by_interval(trials)
    figure, axes = _interval_axes(intervals)
    for axis, intervals_label in zip(axes, intervals):
        series = series_by_interval.get(intervals_label, {})
        colors = _threshold_colors(len(series))
        for (label, thresholds), color in zip(series.items(), colors):
            x_values, y_values = _acceptance_curve(thresholds)
            axis.step(
                x_values,
                y_values,
                where="post",
                linewidth=1.8,
                color=color,
                label=label,
            )
        axis.set_title(intervals_label)
        axis.set_xlabel("candidate tolerance sigmas")
        axis.set_ylabel("fraction accepted")
        axis.set_ylim(0.0, 1.0)
        axis.grid(True, alpha=0.3)
        if 0 < len(series) <= 8:
            axis.legend(fontsize="x-small", frameon=False)

    _hide_unused_axes(axes, len(intervals))
    figure.suptitle("Derived Acceptance Tolerance Sigmas by Interval Policy", fontweight="bold")
    figure.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(figure)


def _threshold_series_by_interval(trials: list[Trial]) -> dict[str, dict[str, list[float]]]:
    series: dict[str, dict[str, list[float]]] = {}
    sorted_trials = sorted(
        trials,
        key=lambda trial: (
            str(trial["intervals"]),
            float(trial["one_probability"]),
            str(trial["r_distribution"]),
            int(trial["trial_index"]),
        ),
    )
    for trial in sorted_trials:
        intervals_label = str(trial["intervals"])
        label = f"p={float(trial['one_probability']):g}, {trial['r_distribution']}"
        series.setdefault(intervals_label, {}).setdefault(label, []).append(
            float(trial["required_acceptance_tolerance_sigmas"])
        )
    return series


def _threshold_colors(series_count: int) -> list:
    if series_count <= 0:
        return []
    if series_count <= 20:
        colormap = plt.get_cmap("tab20")
        return [colormap(index) for index in range(series_count)]
    colormap = plt.get_cmap("nipy_spectral")
    return [colormap((index + 0.5) / series_count) for index in range(series_count)]


def _acceptance_curve(thresholds: list[float]) -> tuple[list[float], list[float]]:
    if not thresholds:
        return [0.0], [0.0]
    candidates = sorted(set(thresholds))
    x_values = [0.0]
    y_values = [_accepted_fraction(thresholds, 0.0)]
    for candidate in candidates:
        x_values.append(candidate)
        y_values.append(_accepted_fraction(thresholds, candidate))
    return x_values, y_values


def _accepted_fraction(thresholds: list[float], candidate: float) -> float:
    return sum(1 for threshold in thresholds if threshold <= candidate) / len(
        thresholds
    )


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


def _interval_axes(intervals: Sequence[str]):
    column_count = min(2, max(len(intervals), 1))
    row_count = ceil(max(len(intervals), 1) / column_count)
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
        label: handle
        for handle, label in zip(handles, labels)
        if label in intervals
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
