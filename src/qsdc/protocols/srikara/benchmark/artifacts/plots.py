"""Matplotlib plot generation for benchmark artifacts."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from itertools import cycle
from pathlib import Path
from typing import Any, Optional, Union

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
THRESHOLD_MARKERS = ("o", "s", "^", "D", "v", "P", "X", "*", "<", ">")


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
        path = plots_dir / spec.filename
        _write_error_bar_plot(path, combos, spec)
        plots.append(str(Path("plots") / spec.filename))

    threshold_path = plots_dir / THRESHOLD_CURVE_FILENAME
    _write_threshold_curve(threshold_path, trials)
    plots.append(str(Path("plots") / THRESHOLD_CURVE_FILENAME))
    return plots


def _write_error_bar_plot(
    path: Path,
    combos: list[Combo],
    spec: ErrorPlotSpec,
) -> None:
    r_labels = _unique_sorted(combo["r_distribution"] for combo in combos)
    probabilities = _unique_sorted(float(combo["one_probability"]) for combo in combos)
    values = _combo_metric_table(combos, spec.metric_field)

    figure, axis = plt.subplots(figsize=(9.5, 5.5), constrained_layout=True)
    positions = list(range(len(r_labels)))
    bar_width = 0.8 / max(len(probabilities), 1)
    for probability_index, probability in enumerate(probabilities):
        offset = (probability_index - (len(probabilities) - 1) / 2) * bar_width
        x_values = [position + offset for position in positions]
        y_values = [
            values.get((r_label, probability), 0.0) for r_label in r_labels
        ]
        axis.bar(
            x_values,
            y_values,
            width=bar_width,
            label=f"p={probability:g}",
        )

    axis.set_title(spec.title)
    axis.set_xlabel("r distribution")
    axis.set_ylabel(spec.y_label)
    axis.set_xticks(positions)
    axis.set_xticklabels(r_labels, rotation=20, ha="right")
    axis.set_ylim(bottom=0.0)
    axis.grid(True, axis="y", alpha=0.3)
    axis.legend(frameon=False)
    figure.savefig(path, dpi=160)
    plt.close(figure)


def _combo_metric_table(
    combos: list[Combo],
    metric_field: str,
) -> dict[tuple[str, float], float]:
    values: dict[tuple[str, float], float] = {}
    for combo in combos:
        y_value = _combo_metric(combo, metric_field)
        if y_value is None:
            continue
        values[
            (
                str(combo["r_distribution"]),
                float(combo["one_probability"]),
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


def _write_threshold_curve(path: Path, trials: list[Trial]) -> None:
    series = _threshold_series(trials)
    figure_height = max(5.5, min(12.0, 4.5 + 0.18 * len(series)))
    figure, axis = plt.subplots(figsize=(10.5, figure_height), constrained_layout=True)
    colors = _threshold_colors(len(series))
    markers = cycle(THRESHOLD_MARKERS)
    for (label, thresholds), color in zip(series.items(), colors):
        x_values, y_values = _acceptance_curve(thresholds)
        marker = next(markers)
        axis.step(
            x_values,
            y_values,
            where="post",
            linewidth=2,
            color=color,
            label=label,
        )
        axis.plot(
            x_values,
            y_values,
            marker=marker,
            color=color,
            linestyle="none",
            markersize=3,
        )

    axis.set_title("Derived Acceptance Tolerance Sigmas Curve")
    axis.set_xlabel("candidate tolerance sigmas")
    axis.set_ylabel("fraction of trials accepted")
    axis.set_ylim(0.0, 1.0)
    axis.grid(True, alpha=0.3)
    axis.legend(
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        fontsize="small",
        frameon=False,
    )
    figure.savefig(path, dpi=160)
    plt.close(figure)


def _threshold_series(trials: list[Trial]) -> dict[str, list[float]]:
    series: dict[str, list[float]] = {}
    sorted_trials = sorted(
        trials,
        key=lambda trial: (
            str(trial["r_distribution"]),
            float(trial["one_probability"]),
            int(trial["trial_index"]),
        ),
    )
    for trial in sorted_trials:
        label = f"p={float(trial['one_probability']):g}, {trial['r_distribution']}"
        series.setdefault(label, []).append(
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


if __name__ == "__main__":
    main()
