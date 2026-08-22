"""Build presentation-only data for the multi-run benchmark index."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from qsdc.protocols.srikara.benchmark.artifacts.ui.utils.formatting import (
    compact_distribution,
    count,
    distribution,
    html_id,
    metric,
    rate,
    run_id,
    text,
)
from qsdc.protocols.srikara.benchmark.artifacts.ui.utils.index_data import (
    best_run_value,
    delta_from_default,
    group_families,
    group_runs,
    non_quick_runs,
    split_group_name,
)


def build_index_context(root: Path, runs: list[dict[str, Any]]) -> dict[str, Any]:
    groups = group_runs(runs)
    families = group_families(groups)
    return {
        "title": f"Srikara benchmark UI: {root.name}",
        "heading": root.name,
        "run_count": len(runs),
        "summary_cards": _summary_cards(runs, families),
        "groups": [_group_view(group) for group in groups],
        "families": [_family_view(family) for family in families],
    }


def _summary_cards(
    runs: list[dict[str, Any]],
    families: list[dict[str, Any]],
) -> list[dict[str, str]]:
    comparable_runs = non_quick_runs(runs)
    cards = [
        ("Runs", len(runs), "benchmark reports found"),
        ("Report families", len(families), "top-level report collections"),
        (
            "Best mean bit error",
            rate(
                best_run_value(
                    comparable_runs,
                    "best_mean_bit",
                    "raw_bit_error_rate",
                )
            ),
            "for p=0.5, excluding quick benchmarks",
        ),
        (
            "Best mean symbol error",
            rate(
                best_run_value(
                    comparable_runs,
                    "best_mean_symbol",
                    "raw_symbol_error_rate",
                )
            ),
            "for p=0.5, excluding quick benchmarks",
        ),
    ]
    return [
        {"title": title, "value": text(value), "detail": detail}
        for title, value, detail in cards
    ]


def _group_view(group: dict[str, Any]) -> dict[str, Any]:
    run = group["latest"]
    return {
        "name": text(group["name"]),
        "id": html_id(group["name"]),
        "report_href": str(run["report_href"]),
        "chips": _configuration_chips(run),
        "scores": [
            _score(
                "LOWEST MEAN BIT ERROR (P=0.5)",
                run["best_mean_bit"],
                "raw_bit_error_rate",
            ),
            _score(
                "LOWEST MEAN SYMBOL ERROR (P=0.5)",
                run["best_mean_symbol"],
                "raw_symbol_error_rate",
            ),
            _score(
                "LOWEST COMBO BIT ERROR (P=0.5)",
                run["best_combo_bit"],
                "raw_bit_error_rate",
                include_distribution=True,
            ),
            _score(
                "LOWEST COMBO SYMBOL ERROR (P=0.5)",
                run["best_combo_symbol"],
                "raw_symbol_error_rate",
                include_distribution=True,
            ),
        ],
        "interval_table": _interval_table(run),
        "recent_runs": [
            {"href": str(item["report_href"]), "label": run_id(item["run_id"])}
            for item in reversed(group["runs"][-5:])
        ],
    }


def _configuration_chips(run: dict[str, Any]) -> list[dict[str, str]]:
    probabilities = " · ".join(f"{value:g}" for value in run["one_probabilities"])
    axes = f"{run['check_axis_policy']} → {run['message_axis_policy']}"
    return [
        {
            "label": "α",
            "value": distribution(run["alpha_distribution"], "alpha"),
        },
        {
            "label": "θ",
            "value": distribution(run["theta_distribution"], "theta"),
        },
        {"label": "One probability", "value": probabilities},
        {"label": "Axes", "value": axes},
    ]


def _score(
    title: str,
    row: dict[str, Any] | None,
    metric_name: str,
    include_distribution: bool = False,
) -> dict[str, str]:
    if row is None:
        return {"title": title, "value": "n/a", "detail": "n/a"}
    detail = text(row.get("intervals"))
    if include_distribution and row.get("r_distribution") not in ("", None):
        detail = f"{detail}, r={compact_distribution(row['r_distribution'])}"
    return {
        "title": title,
        "value": metric(metric_name, row.get(metric_name)),
        "detail": detail,
    }


def _interval_table(run: dict[str, Any]) -> dict[str, Any]:
    rows = run["interval_rows"]
    return {
        "headers": ["intervals", "bit error (p=0.5)", "symbol error (p=0.5)"],
        "rows": [
            [
                _cell(row["intervals"], strong=True),
                _metric_cell(row, rows, "balanced_bit_error_rate"),
                _metric_cell(row, rows, "balanced_symbol_error_rate"),
            ]
            for row in rows
        ],
    }


def _family_view(family: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": text(family["name"]),
        "report_count": count(len(family["report_groups"]), "report"),
        "run_count": count(family["run_count"], "run"),
        "navigation": [
            {
                "id": html_id(group["name"]),
                "label": split_group_name(str(group["name"]))[1],
            }
            for group in family["report_groups"]
        ],
        "history_table": _history_table(family),
    }


def _history_table(family: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for group in family["report_groups"]:
        for run in reversed(group["runs"]):
            rows.append(
                [
                    _cell(run["report_name"]),
                    _cell(run_id(run["run_id"]), href=str(run["report_href"])),
                    _cell(run["backend"]),
                    _cell(_interval_policy_summary(run["interval_policies"])),
                    _cell(_axis_summary(run)),
                    _cell(run["trial_count"]),
                    _cell(rate(run["accepted_rate"])),
                    _cell(rate(run["mean_bit_error_rate"])),
                    _cell(rate(run["mean_symbol_error_rate"])),
                ]
            )
    return {
        "headers": [
            "configuration",
            "run",
            "backend",
            "intervals",
            "axes",
            "trials",
            "accepted",
            "mean bit error",
            "mean symbol error",
        ],
        "rows": rows,
    }


def _metric_cell(
    row: dict[str, Any],
    rows: list[dict[str, Any]],
    field: str,
) -> dict[str, Any]:
    delta = delta_from_default(row, rows, field)
    delta_view = None
    if delta:
        delta_view = {
            "class_name": "delta-good" if delta > 0 else "delta-bad",
            "marker": "▼" if delta > 0 else "▲",
            "text": rate(abs(delta)),
        }
    return {"text": rate(row.get(field)), "metric": True, "delta": delta_view}


def _cell(
    value: object,
    *,
    href: str | None = None,
    strong: bool = False,
) -> dict[str, Any]:
    return {"text": text(value), "href": href, "strong": strong}


def _axis_summary(run: dict[str, Any]) -> str:
    check_axis = str(run["check_axis_policy"])
    message_axis = str(run["message_axis_policy"])
    return (
        check_axis if check_axis == message_axis else f"{check_axis} / {message_axis}"
    )


def _interval_policy_summary(policies: list[object]) -> str:
    return str(policies[0]) if len(policies) == 1 else f"{len(policies)} policies"
