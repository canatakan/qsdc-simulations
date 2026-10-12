from __future__ import annotations

from pathlib import Path
from textwrap import fill

import numpy as np
from matplotlib import colormaps
from matplotlib.axes import Axes
from matplotlib.axis import Axis
from matplotlib.figure import Figure
from matplotlib.patches import Patch
from matplotlib.ticker import PercentFormatter

from qsdc.protocols.srikara.benchmark.benchmark import BenchmarkResult, RunResult

PLOTTED = {
    "bit_error_rate": "Bit error rate",
    "delivered_bits_per_state": "Delivered bits / state",
    "information_per_state": "Raw-symbol MI / state",
    "rejection_rate": "Sends rejected by the checks",
}
HEATMAP_METRICS = ("bit_error_rate", "delivered_bits_per_state")


def write_plots(
    result: BenchmarkResult, labels: list[str], directory: Path
) -> list[str]:
    layout = result.benchmark.layout
    if layout == "heatmap":
        figures = {
            f"heatmap_{i}.png": figure
            for i, figure in enumerate(_heatmaps(result), start=1)
        }
    elif layout == "sweep":
        figures = {"sweep.png": _sweep(result)}
    else:
        figures = {"comparison.png": _comparison(result, labels)}
    for name, figure in figures.items():
        figure.savefig(directory / name, dpi=150, bbox_inches="tight")
    return list(figures)


def _comparison(result: BenchmarkResult, labels: list[str]) -> Figure:
    runs = result.runs
    labels = [fill(label, 40) for label in labels]
    series = list(dict.fromkeys(run.case.series for run in runs))
    colors = [colormaps["tab10"](series.index(run.case.series) % 10) for run in runs]
    height = max(6.0, 0.6 * sum(label.count("\n") + 1 for label in labels))
    figure = Figure(figsize=(15, height), layout="constrained")
    axes = figure.subplots(2, 2, sharey=True)
    positions = np.arange(len(runs))
    for axis, (metric, title) in zip(axes.flat, PLOTTED.items()):
        values = [_value(run, metric) for run in runs]
        errors = np.nan_to_num([run.interval(metric) for run in runs])
        axis.barh(
            positions,
            np.nan_to_num(values),
            xerr=errors,
            color=colors,
            error_kw={"capsize": 3, "elinewidth": 1},
        )
        highest = np.nanmax([0.0, *(np.nan_to_num(values) + errors)])
        right = max(0.01, 1.25 * highest)
        wide = errors.max(initial=0.0) > 0.05 * right
        for position, value, error in zip(positions, values, errors):
            value = np.nan_to_num(value)
            inside = wide and value - error > 0.3 * right
            axis.annotate(
                _format(metric, value),
                (value - error, position) if inside else (value + error, position),
                xytext=(-6, 0) if inside else (4, 0),
                textcoords="offset points",
                ha="right" if inside else "left",
                va="center",
                color="white" if inside else "black",
            )
        axis.set_yticks(positions, labels)
        axis.set_xlim(0.0, right)
        _style(axis, title, metric, axis.xaxis)
    axes[0, 0].invert_yaxis()
    if len(series) > 1:
        figure.legend(
            handles=[
                Patch(color=colormaps["tab10"](i % 10), label=name)
                for i, name in enumerate(series)
            ],
            loc="outside lower center",
            ncols=len(series),
            frameon=False,
        )
    figure.suptitle(_title(result), fontsize=16, fontweight="bold")
    return figure


def _sweep(result: BenchmarkResult) -> Figure:
    runs = result.runs
    series = list(dict.fromkeys(run.case.series for run in runs))
    figure = Figure(figsize=(12, 8), layout="constrained")
    axes = figure.subplots(2, 2)
    for axis, (metric, title) in zip(axes.flat, PLOTTED.items()):
        for name in series:
            points = sorted(
                (*run.case.at, _value(run, metric), run.interval(metric))
                for run in runs
                if run.case.series == name
            )
            x, y, error = (np.array(column) for column in zip(*points))
            error = np.nan_to_num(error)
            line = axis.plot(x, y, marker="o", linewidth=2.0, label=name)[0]
            axis.fill_between(
                x, y - error, y + error, color=line.get_color(), alpha=0.2, linewidth=0
            )
        axis.set_xlabel(result.benchmark.axes[0])
        axis.set_xticks(sorted({run.case.at[0] for run in runs}))
        axis.set_ylim(0.0, max(0.01, axis.get_ylim()[1]))
        _style(axis, title, metric, axis.yaxis)
        if len(series) > 1:
            axis.legend(frameon=False)
    figure.suptitle(_title(result), fontsize=16, fontweight="bold")
    return figure


def _heatmaps(result: BenchmarkResult) -> list[Figure]:
    runs = result.runs
    limits = {
        metric: _limits([_value(run, metric) for run in runs])
        for metric in HEATMAP_METRICS
    }
    figures = []
    for series in dict.fromkeys(run.case.series for run in runs):
        cells = {run.case.at: run for run in runs if run.case.series == series}
        xs, ys = sorted({x for x, _ in cells}), sorted({y for _, y in cells})
        figure = Figure(figsize=(12, 4.8), layout="constrained")
        axes = figure.subplots(1, 2)
        for axis, metric in zip(axes, HEATMAP_METRICS):
            matrix = np.array(
                [
                    [
                        _value(cells[x, y], metric) if (x, y) in cells else np.nan
                        for x in xs
                    ]
                    for y in ys
                ]
            )
            colormap = "viridis" if metric.endswith("per_state") else "viridis_r"
            image = axis.imshow(
                np.ma.masked_invalid(matrix),
                origin="lower",
                aspect="auto",
                cmap=colormap,
                vmin=limits[metric][0],
                vmax=limits[metric][1],
            )
            for (row, column), value in np.ndenumerate(matrix):
                red, green, blue, _ = image.cmap(image.norm(value))
                dark = 0.2126 * red + 0.7152 * green + 0.0722 * blue < 0.5
                axis.text(
                    column,
                    row,
                    _format(metric, value),
                    ha="center",
                    va="center",
                    fontsize=9,
                    color="white" if dark else "black",
                )
            axis.set_xticks(range(len(xs)), [f"{x:g}" for x in xs])
            axis.set_yticks(range(len(ys)), [f"{y:g}" for y in ys])
            axis.set_xlabel(result.benchmark.axes[0])
            axis.set_ylabel(result.benchmark.axes[1])
            axis.set_title(PLOTTED[metric], fontweight="bold")
            colorbar = figure.colorbar(image, ax=axis, fraction=0.046, pad=0.04)
            if not metric.endswith("per_state"):
                colorbar.formatter = PercentFormatter(1.0, decimals=1)
                colorbar.update_ticks()
        figure.suptitle(f"{_title(result)} · {series}", fontsize=16, fontweight="bold")
        figures.append(figure)
    return figures


def _style(axis: Axes, title: str, metric: str, value_axis: Axis) -> None:
    axis.set_title(title, fontweight="bold")
    axis.grid(alpha=0.3)
    if not metric.endswith("per_state"):
        value_axis.set_major_formatter(PercentFormatter(1.0))


def _title(result: BenchmarkResult) -> str:
    return result.benchmark.name.replace("_", " ").capitalize()


def _value(run: RunResult, metric: str) -> float:
    value = getattr(run.metrics, metric)
    return np.nan if value is None else value


def _format(metric: str, value: float) -> str:
    if np.isnan(value):
        return "—"
    return f"{value:.3f}" if metric.endswith("per_state") else f"{value:.2%}"


def _limits(values: list[float]) -> tuple[float, float]:
    finite = [value for value in values if np.isfinite(value)]
    return (min(finite), max(finite)) if finite else (0.0, 1.0)
