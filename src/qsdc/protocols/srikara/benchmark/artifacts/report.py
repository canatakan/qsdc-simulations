"""Static HTML report writer for benchmark summaries."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from qsdc.protocols.srikara.benchmark.artifacts.tables import (
    COMBO_FIELDS,
    TRIAL_FIELDS,
    combo_csv_rows,
    trial_csv_rows,
)
from qsdc.protocols.srikara.benchmark.artifacts.ui import (
    copy_asset,
    render_template,
)
from qsdc.protocols.srikara.benchmark.artifacts.ui.formatting import (
    human_header,
    number,
    rate,
    run_id,
    table_cell,
    text,
)


Combo = dict[str, Any]
Trial = dict[str, Any]

_COMBO_OUTCOME_FIELDS = (
    "combo_index",
    "intervals",
    "one_probability",
    "r_distribution",
    "accepted_count",
    "accepted_rate",
    "bit_error_rate",
    "symbol_error_rate",
    "mean_abs_value_error",
)

_CHECK_FAILURE_FIELDS = (
    "combo_index",
    "intervals",
    "one_probability",
    "r_distribution",
    "control_failed_check_count",
    "control_failed_check_rate",
    "decoy_failed_check_count",
    "decoy_failed_check_rate",
)


def write_benchmark_html_report(
    output_dir: str | Path,
    summary: dict[str, Any],
    combos: list[Combo],
    trials: list[Trial],
) -> str:
    """Write a self-contained benchmark report and its stylesheet."""
    output_path = Path(output_dir)
    copy_asset("report.css", output_path / "report.css")
    (output_path / "report.html").write_text(
        _render_report(summary, combos, trials),
        encoding="utf-8",
    )
    return "report.html"


def _render_report(
    summary: dict[str, Any],
    combos: list[Combo],
    trials: list[Trial],
) -> str:
    combo_rows = _combo_table_rows(combos)
    return render_template(
        "report.html",
        title=f"{summary.get('name')} benchmark report",
        name=text(summary.get("name")),
        run_id=run_id(summary.get("benchmark_run_id")),
        run_meta=_run_meta(summary),
        summary_cards=_summary_cards(summary, combos),
        context_items=_context_items(summary),
        plots=_plot_rows(summary.get("artifacts", {}).get("plots", [])),
        combo_outcomes=_table(_COMBO_OUTCOME_FIELDS, combo_rows),
        check_failures=_table(_CHECK_FAILURE_FIELDS, combo_rows),
        combo_table=_table(COMBO_FIELDS, combo_rows),
        trial_table=_table(TRIAL_FIELDS, _trial_table_rows(trials)),
        artifact_links=_artifact_links(summary),
    )


def _run_meta(summary: dict[str, Any]) -> list[dict[str, str]]:
    parameters = summary.get("parameters", {})
    return _labeled_values(
        [
            ("Backend", parameters.get("backend")),
            ("Random source", parameters.get("random_source")),
            ("Axis policies", _axis_policy_summary(parameters)),
            ("Trials", summary.get("trial_count")),
            ("Combos", summary.get("combo_count")),
        ]
    )


def _context_items(summary: dict[str, Any]) -> list[dict[str, str]]:
    parameters = summary.get("parameters", {})
    counts = summary.get("derived_counts", {})
    return _labeled_values(
        [
            ("interval policies", parameters.get("interval_policies", ["default"])),
            ("noise", parameters.get("noise")),
            ("alpha", parameters.get("alpha_distribution")),
            ("theta", parameters.get("theta_distribution")),
            ("payload bits", counts.get("payload_bit_count")),
            ("padding bits", counts.get("padding_bit_count")),
            ("transmitted bits", counts.get("transmitted_message_bit_count")),
            ("3-bit symbols", counts.get("message_symbol_count")),
            ("states", counts.get("n_states")),
        ]
    )


def _labeled_values(rows: list[tuple[str, object]]) -> list[dict[str, str]]:
    return [{"label": label, "value": text(value)} for label, value in rows]


def _axis_policy_summary(parameters: dict[str, Any]) -> str:
    check_policy = parameters.get("check_axis_policy", "random")
    message_policy = parameters.get("message_axis_policy", "random")
    if check_policy == message_policy:
        return str(check_policy)
    return f"check={check_policy}, message={message_policy}"


def _summary_cards(
    summary: dict[str, Any],
    combos: list[Combo],
) -> list[dict[str, str]]:
    balanced_combos = _balanced_combos(combos)
    balanced_detail = _balanced_metric_detail(balanced_combos)
    return [
        _card(
            "Accepted trials",
            rate(summary.get("accepted_rate")),
            f"{summary.get('accepted_count')} accepted",
        ),
        _card(
            "Mean bit error",
            rate(_weighted_combo_metric(balanced_combos, "bit_error_rate")),
            balanced_detail,
        ),
        _card(
            "Mean symbol error",
            rate(_weighted_combo_metric(balanced_combos, "symbol_error_rate")),
            balanced_detail,
        ),
        _card(
            "Mean numeric error",
            number(_weighted_combo_metric(balanced_combos, "mean_abs_value_error")),
            balanced_detail,
        ),
    ]


def _card(title: str, value: str, detail: str) -> dict[str, str]:
    return {"title": title, "value": value, "detail": detail}


def _plot_cards(plots: object) -> str:
    """Render plot cards; retained as a small compatibility/test seam."""
    return render_template("report/plots.html", plots=_plot_rows(plots))


def _plot_rows(plots: object) -> list[dict[str, str]]:
    if not isinstance(plots, list):
        return []
    return [
        {
            "path": str(plot),
            "title": Path(str(plot)).stem.replace("_", " "),
        }
        for plot in plots
        if "delta_vs_default" not in Path(str(plot)).stem
    ]


def _artifact_links(summary: dict[str, Any]) -> list[str]:
    artifacts = summary.get("artifacts", {})
    return [
        str(path)
        for path in (
            artifacts.get("benchmark"),
            artifacts.get("combos_csv"),
            artifacts.get("trials_csv"),
        )
        if path
    ]


def _table(
    fields: tuple[str, ...] | list[str],
    rows: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "headers": [human_header(field) for field in fields],
        "rows": [
            [{"text": table_cell(field, row.get(field))} for field in fields]
            for row in rows
        ],
    }


def _balanced_combos(combos: list[Combo]) -> list[Combo]:
    return [
        combo
        for combo in combos
        if combo.get("one_probability") not in ("", None)
        and float(combo["one_probability"]) == 0.5
    ]


def _weighted_combo_metric(combos: list[Combo], metric_name: str) -> float | None:
    weighted_total = 0.0
    total_weight = 0.0
    for combo in combos:
        value = _combo_metric_value(combo, metric_name)
        if value in ("", None):
            continue
        weight = float(combo.get("trial_count") or 1.0)
        weighted_total += float(value) * weight
        total_weight += weight
    return weighted_total / total_weight if total_weight else None


def _balanced_metric_detail(combos: list[Combo]) -> str:
    noun = "combination" if len(combos) == 1 else "combinations"
    return f"trial-weighted at p=0.5 across {len(combos)} {noun}"


def _combo_metric_value(combo: Combo, metric_name: str) -> object:
    if metric_name in combo:
        return combo[metric_name]
    return combo.get("all", {}).get(metric_name)


def _combo_table_rows(combos: list[Combo]) -> list[dict[str, object]]:
    if combos and "all" in combos[0]:
        return combo_csv_rows(combos)
    return combos


def _trial_table_rows(trials: list[Trial]) -> list[dict[str, object]]:
    if trials and "message_bit_count" in trials[0]:
        return trial_csv_rows(trials)
    return trials
