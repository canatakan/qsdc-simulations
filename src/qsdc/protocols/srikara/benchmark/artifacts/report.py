"""Static HTML report writer for benchmark summaries."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from qsdc.protocols.srikara.benchmark.artifacts.tables import (
    COMBO_FIELDS,
    TRIAL_FIELDS,
    combo_csv_rows,
    trial_csv_rows,
)
from qsdc.protocols.srikara.benchmark.artifacts.ui import read_template


Combo = dict[str, Any]
Trial = dict[str, Any]


def write_benchmark_html_report(
    output_dir: str | Path,
    summary: dict[str, Any],
    combos: list[Combo],
    trials: list[Trial],
) -> str:
    output_path = Path(output_dir)
    (output_path / "report.css").write_text(
        read_template("report.css"),
        encoding="utf-8",
    )
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
    template = read_template("report.html")
    replacements = {
        "title": _text(f"{summary.get('name')} benchmark report"),
        "name": _text(summary.get("name")),
        "run_id": _text(_format_run_id(summary.get("benchmark_run_id"))),
        "run_meta": _run_meta(summary),
        "context": _context_panel(summary, combos),
        "cards": _summary_cards(summary, combos),
        "plots": _plot_cards(summary.get("artifacts", {}).get("plots", [])),
        "combo_outcomes": _table(
            _COMBO_OUTCOME_FIELDS,
            _select_table_fields(_combo_table_rows(combos), _COMBO_OUTCOME_FIELDS),
        ),
        "check_failures": _table(
            _CHECK_FAILURE_FIELDS,
            _select_table_fields(_combo_table_rows(combos), _CHECK_FAILURE_FIELDS),
        ),
        "combo_table": _table(_RAW_COMBO_FIELDS, _combo_table_rows(combos)),
        "trial_table": _table(TRIAL_FIELDS, _trial_table_rows(trials)),
        "artifact_links": _artifact_links(summary),
    }
    return _replace_placeholders(template, replacements)


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

_RAW_COMBO_FIELDS = COMBO_FIELDS


def _run_meta(summary: dict[str, Any]) -> str:
    parameters = summary.get("parameters", {})
    rows = [
        ("Backend", parameters.get("backend")),
        ("Random source", parameters.get("random_source")),
        ("Axis policies", _axis_policy_summary(parameters)),
        ("Trials", summary.get("trial_count")),
        ("Combos", summary.get("combo_count")),
    ]
    return "\n".join(
        f"<div><dt>{escape(label)}</dt><dd>{_text(value)}</dd></div>"
        for label, value in rows
    )


def _context_panel(summary: dict[str, Any], combos: list[Combo]) -> str:
    parameters = summary.get("parameters", {})
    derived_counts = summary.get("derived_counts", {})
    rows = [
        ("interval policies", parameters.get("interval_policies", ["default"])),
        ("alpha", _distribution_body(parameters.get("alpha_distribution"))),
        ("theta", _distribution_body(parameters.get("theta_distribution"))),
        ("payload bits", derived_counts.get("payload_bit_count")),
        ("padding bits", derived_counts.get("padding_bit_count")),
        ("transmitted bits", derived_counts.get("transmitted_message_bit_count")),
        ("3-bit symbols", derived_counts.get("message_symbol_count")),
        ("states", derived_counts.get("n_states")),
    ]
    items = "\n".join(
        f"""
        <div class="context-item">
          <span>{escape(label)}</span>
          <strong>{_text(value)}</strong>
        </div>
        """
        for label, value in rows
    )
    return f'<div class="context-grid">{items}</div>'


def _axis_policy_summary(parameters: dict[str, Any]) -> str:
    check_policy = parameters.get("check_axis_policy", "random")
    message_policy = parameters.get("message_axis_policy", "random")
    if check_policy == message_policy:
        return str(check_policy)
    return f"check={check_policy}, message={message_policy}"


def _summary_cards(summary: dict[str, Any], combos: list[Combo]) -> str:
    balanced_combos = _balanced_combos(combos)
    balanced_detail = _balanced_metric_detail(balanced_combos)
    cards = [
        (
            "Accepted trials",
            _format_rate(summary.get("accepted_rate")),
            f"{summary.get('accepted_count')} accepted",
        ),
        (
            "Mean bit error",
            _format_rate(_weighted_combo_metric(balanced_combos, "bit_error_rate")),
            balanced_detail,
        ),
        (
            "Mean symbol error",
            _format_rate(
                _weighted_combo_metric(balanced_combos, "symbol_error_rate")
            ),
            balanced_detail,
        ),
        (
            "Mean numeric error",
            _format_number(
                _weighted_combo_metric(balanced_combos, "mean_abs_value_error")
            ),
            balanced_detail,
        ),
    ]
    return "\n".join(_summary_card(title, value, detail) for title, value, detail in cards)


def _summary_card(title: str, value: object, detail: str) -> str:
    return f"""
      <article class="card">
        <h2>{escape(title)}</h2>
        <p class="card-value">{_text(value)}</p>
        <p>{escape(detail)}</p>
      </article>
    """


def _plot_cards(plots: object) -> str:
    if not isinstance(plots, list) or not plots:
        return '<p class="muted">No plots were generated.</p>'
    cards = []
    for plot in plots:
        plot_path = str(plot)
        if "delta_vs_default" in Path(plot_path).stem:
            continue
        title = Path(plot_path).stem.replace("_", " ")
        cards.append(
            f"""
          <figure class="plot-card">
            <img src="{escape(plot_path)}" alt="{escape(title)}">
            <figcaption>{escape(title)}</figcaption>
          </figure>
            """
        )
    if not cards:
        return '<p class="muted">No plots were generated.</p>'
    return "\n".join(cards)


def _artifact_links(summary: dict[str, Any]) -> str:
    artifacts = summary.get("artifacts", {})
    links = [
        artifacts.get("benchmark"),
        artifacts.get("combos_csv"),
        artifacts.get("trials_csv"),
    ]
    return "\n".join(
        f'<a href="{escape(str(path))}">{escape(str(path))}</a>'
        for path in links
        if path
    )


def _table(headers: tuple[str, ...] | list[str], rows: list[dict[str, object]]) -> str:
    header_html = "".join(
        f"<th>{escape(_human_header(header))}</th>" for header in headers
    )
    row_html = "\n".join(
        "<tr>"
        + "".join(
            f"<td>{_format_cell(header, row.get(header))}</td>"
            for header in headers
        )
        + "</tr>"
        for row in rows
    )
    return f"""
      <div class="table-wrap">
        <table>
          <thead><tr>{header_html}</tr></thead>
          <tbody>{row_html}</tbody>
        </table>
      </div>
    """


def _balanced_combos(combos: list[Combo]) -> list[Combo]:
    return [
        combo
        for combo in combos
        if combo.get("one_probability") not in ("", None)
        and float(combo["one_probability"]) == 0.5
    ]


def _weighted_combo_metric(combos: list[Combo], metric: str) -> float | None:
    weighted_total = 0.0
    total_weight = 0.0
    for combo in combos:
        value = _combo_metric_value(combo, metric)
        if value in ("", None):
            continue
        weight = float(combo.get("trial_count") or 1.0)
        weighted_total += float(value) * weight
        total_weight += weight
    return weighted_total / total_weight if total_weight else None


def _balanced_metric_detail(combos: list[Combo]) -> str:
    count = len(combos)
    noun = "combination" if count == 1 else "combinations"
    return f"trial-weighted at p=0.5 across {count} {noun}"


def _combo_metric_value(combo: Combo, metric: str) -> object:
    if metric in combo:
        return combo[metric]
    return combo.get("all", {}).get(metric)


def _combo_table_rows(combos: list[Combo]) -> list[dict[str, object]]:
    if combos and "all" in combos[0]:
        return combo_csv_rows(combos)
    return combos


def _trial_table_rows(trials: list[Trial]) -> list[dict[str, object]]:
    if trials and "message_bit_count" in trials[0]:
        return trial_csv_rows(trials)
    return trials


def _select_table_fields(
    rows: list[dict[str, object]],
    fields: tuple[str, ...],
) -> list[dict[str, object]]:
    return [{field: row.get(field) for field in fields} for row in rows]


def _format_rate(value: object) -> str:
    if value is None:
        return "n/a"
    return f"{100.0 * float(value):.2f}%"


def _format_number(value: object) -> str:
    if value is None:
        return "n/a"
    number = float(value)
    if number == 0.0:
        return "0"
    if abs(number) < 1e-4 or abs(number) >= 1e5:
        return f"{number:.6e}"
    return f"{number:.6g}"


def _format_run_id(value: object) -> str:
    if value is None:
        return "n/a"
    run_id = str(value)
    if run_id.startswith("run_"):
        return f"#{run_id.removeprefix('run_')}"
    return f"#{run_id}" if run_id.isdigit() else run_id


def _distribution_body(value: object) -> object:
    return value


def _text(value: object) -> str:
    if value is None:
        return "n/a"
    return escape(str(value))


def _human_header(header: str) -> str:
    replacements = {
        "r_distribution": "r",
        "one_probability": "one probability",
        "mean_abs_value_error": "mean absolute numeric error",
    }
    return replacements.get(header, header.replace("_", " "))


def _format_cell(header: str, value: object) -> str:
    if value is None:
        return "n/a"
    if _is_identifier_field(header):
        return _format_identifier(value)
    if header.endswith("_rate"):
        return _format_rate(value)
    if isinstance(value, bool):
        return "yes" if value else "no"
    if _looks_numeric(value):
        return _format_number(value)
    return _text(value)


def _is_identifier_field(header: str) -> bool:
    return (
        header.endswith("_seed")
        or header.endswith("_index")
        or header.endswith("_count")
    )


def _format_identifier(value: object) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return _text(value)
    if number.is_integer():
        return escape(str(int(number)))
    return _text(value)


def _looks_numeric(value: object) -> bool:
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


def _replace_placeholders(template: str, replacements: dict[str, object]) -> str:
    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace("{{ " + key + " }}", str(value))
    return rendered
