"""Static multi-run benchmark UI generator."""

from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path
from typing import Any

from qsdc.protocols.srikara.benchmark.artifacts.tables import read_combo_csv
from qsdc.protocols.srikara.benchmark.artifacts.ui import read_template


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results_dir", help="directory containing benchmark run folders")
    args = parser.parse_args()

    index_path = write_benchmark_index(args.results_dir)
    print(f"Generated benchmark UI at {index_path}")


def write_benchmark_index(results_dir: str | Path) -> str:
    root = Path(results_dir)
    root.mkdir(parents=True, exist_ok=True)
    runs = _find_runs(root)
    (root / "index.css").write_text(read_template("index.css"), encoding="utf-8")
    (root / "index.html").write_text(
        _render_index(root, runs),
        encoding="utf-8",
    )
    return str(root / "index.html")


def _find_runs(root: Path) -> list[dict[str, Any]]:
    runs = []
    for benchmark_path in sorted(root.rglob("benchmark.json")):
        run_dir = benchmark_path.parent
        with benchmark_path.open("r", encoding="utf-8") as handle:
            summary = json.load(handle)
        combos_path = run_dir / "combos.csv"
        combos = read_combo_csv(combos_path) if combos_path.exists() else []
        runs.append(_run_row(root, run_dir, summary, combos))
    return sorted(
        runs,
        key=lambda run: (
            str(run["name"]),
            str(run["interval_policies"]),
            str(run["check_axis_policy"]),
            str(run["message_axis_policy"]),
            str(run["alpha_distribution"]),
            str(run["theta_distribution"]),
            str(run["run_id"]),
        ),
    )


def _run_row(
    root: Path,
    run_dir: Path,
    summary: dict[str, Any],
    combos: list[dict[str, Any]],
) -> dict[str, Any]:
    parameters = summary.get("parameters", {})
    artifacts = summary.get("artifacts", {})
    report_path = run_dir / str(artifacts.get("html_report", "report.html"))
    interval_rows = _interval_rows(combos)
    return {
        "name": summary.get("name"),
        "run_id": summary.get("benchmark_run_id"),
        "run_order": _run_order(summary.get("benchmark_run_id")),
        "backend": parameters.get("backend"),
        "interval_policies": parameters.get("interval_policies", ["default"]),
        "check_axis_policy": parameters.get("check_axis_policy"),
        "message_axis_policy": parameters.get("message_axis_policy"),
        "alpha_distribution": parameters.get("alpha_distribution"),
        "theta_distribution": parameters.get("theta_distribution"),
        "one_probabilities": _unique_sorted(
            float(combo["one_probability"])
            for combo in combos
            if combo.get("one_probability") not in ("", None)
        ),
        "interval_rows": interval_rows,
        "best_accepted": _best_interval_row(interval_rows, "accepted_rate", max),
        "best_symbol": _best_interval_row(interval_rows, "symbol_error_rate", min),
        "best_numeric": _best_interval_row(interval_rows, "mean_abs_value_error", min),
        "best_required_sigmas": _best_interval_row(
            interval_rows,
            "required_acceptance_tolerance_sigmas_p95",
            min,
        ),
        "symbol_error_delta": _metric_delta_against_default(
            interval_rows,
            "symbol_error_rate",
            min,
        ),
        "accepted_rate": summary.get("accepted_rate"),
        "trial_count": summary.get("trial_count"),
        "combo_count": summary.get("combo_count"),
        "max_symbol_error_rate": _max_combo_metric(combos, "symbol_error_rate"),
        "max_mean_abs_value_error": _max_combo_metric(combos, "mean_abs_value_error"),
        "max_required_tolerance_sigmas": _max_combo_metric(
            combos,
            "required_acceptance_tolerance_sigmas_max",
        ),
        "max_check_failure_rate": max(
            _max_combo_metric(combos, "control_failed_check_rate") or 0.0,
            _max_combo_metric(combos, "decoy_failed_check_rate") or 0.0,
        ),
        "report_href": report_path.relative_to(root),
    }


def _render_index(root: Path, runs: list[dict[str, Any]]) -> str:
    groups = _run_groups(runs)
    template = read_template("index.html")
    replacements = {
        "title": _text(f"Srikara benchmark UI: {root.name}"),
        "heading": _text(root.name),
        "run_count": len(runs),
        "cards": _cards(runs),
        "group_nav": _group_nav(groups),
        "group_sections": _group_sections(groups),
        "run_table": _run_table(runs),
    }
    return _replace_placeholders(template, replacements)


def _cards(runs: list[dict[str, Any]]) -> str:
    groups = _run_groups(runs)
    return "\n".join(
        [
            _card("Runs", len(runs), "benchmark reports found"),
            _card("Families", len(groups), "comparable benchmark groups"),
            _card(
                "Best accepted trials",
                _best_rate(runs, "accepted_rate"),
                "highest accepted-trial rate",
            ),
            _card(
                "Best interval delta",
                _best_symbol_delta(runs),
                "largest symbol-error drop from default",
            ),
        ]
    )


def _card(title: str, value: object, detail: str) -> str:
    return f"""
      <article class="card">
        <h2>{escape(title)}</h2>
        <p class="card-value">{_text(value)}</p>
        <p>{escape(detail)}</p>
      </article>
    """


def _run_groups(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        grouped.setdefault(str(run["name"]), []).append(run)
    groups = []
    for name, group_runs in grouped.items():
        ordered_runs = sorted(group_runs, key=lambda run: run["run_order"])
        groups.append(
            {
                "name": name,
                "runs": ordered_runs,
                "latest": ordered_runs[-1],
            }
        )
    return sorted(groups, key=lambda group: str(group["name"]))


def _group_nav(groups: list[dict[str, Any]]) -> str:
    if not groups:
        return '<p class="muted">No benchmark groups found.</p>'
    return "\n".join(
        f'<a href="#{escape(_group_id(group["name"]))}">{_text(group["name"])}</a>'
        for group in groups
    )


def _group_sections(groups: list[dict[str, Any]]) -> str:
    if not groups:
        return '<section class="panel"><p class="muted">No benchmark runs found.</p></section>'
    return "\n".join(_group_section(group) for group in groups)


def _group_section(group: dict[str, Any]) -> str:
    run = group["latest"]
    score_cards = "\n".join(
        [
            _score_card("best symbol error", run["best_symbol"], "symbol_error_rate"),
            _score_card(
                "best numeric error",
                run["best_numeric"],
                "mean_abs_value_error",
            ),
            _score_card("highest accepted", run["best_accepted"], "accepted_rate"),
            _score_card(
                "best p95 sigmas",
                run["best_required_sigmas"],
                "required_acceptance_tolerance_sigmas_p95",
            ),
        ]
    )
    history = " ".join(
        (
            f'<a href="{escape(str(item["report_href"]))}">'
            f'{_format_run_id(item["run_id"])}</a>'
        )
        for item in reversed(group["runs"][-5:])
    )
    return f"""
      <section class="panel" id="{escape(_group_id(group["name"]))}">
        <div class="panel-header">
          <div>
            <h2>{_text(group["name"])}</h2>
            <p>{_group_detail(run)}</p>
          </div>
          <a class="button" href="{escape(str(run["report_href"]))}">open latest report</a>
        </div>
        <div class="score-grid">
          {score_cards}
        </div>
        {_interval_table(run)}
        <div class="run-history"><span>recent runs</span>{history}</div>
      </section>
    """


def _group_detail(run: dict[str, Any]) -> str:
    policies = ", ".join(str(value) for value in run["interval_policies"])
    probabilities = ", ".join(f"{value:g}" for value in run["one_probabilities"])
    return escape(
        "intervals: "
        f"{policies}; p: {probabilities}; "
        f"axis: {run['check_axis_policy']}/{run['message_axis_policy']}"
    )


def _score_card(title: str, row: dict[str, Any] | None, metric: str) -> str:
    if row is None:
        value = "n/a"
        detail = "n/a"
    else:
        value = _format_metric(metric, row.get(metric))
        detail = str(row.get("intervals", "n/a"))
    return f"""
      <article>
        <span>{escape(title)}</span>
        <strong>{_text(value)}</strong>
        <em>{_text(detail)}</em>
      </article>
    """


def _interval_table(run: dict[str, Any]) -> str:
    headers = [
        "intervals",
        "accepted",
        "symbol error",
        "numeric error",
        "required sigmas p95",
        "symbol delta",
    ]
    rows = []
    for row in run["interval_rows"]:
        rows.append(
            [
                f'<strong>{_text(row["intervals"])}</strong>',
                _format_rate(row.get("accepted_rate")),
                _format_rate(row.get("symbol_error_rate")),
                _format_number(row.get("mean_abs_value_error")),
                _format_number(row.get("required_acceptance_tolerance_sigmas_p95")),
                _format_signed_rate(
                    _delta_from_default(
                        row,
                        run["interval_rows"],
                        "symbol_error_rate",
                    )
                ),
            ]
        )
    return _table(headers, rows, "comparison-table")


def _run_table(runs: list[dict[str, Any]]) -> str:
    headers = [
        "name",
        "run",
        "backend",
        "interval policies",
        "check axis",
        "message axis",
        "alpha",
        "theta",
        "trials",
        "combos",
        "report",
        "accepted trials",
        "max symbol error",
        "max numeric error",
        "max required sigmas",
        "max check fail",
    ]
    rows = []
    for run in runs:
        rows.append(
            [
                run["name"],
                _format_run_id(run["run_id"]),
                run["backend"],
                run["interval_policies"],
                run["check_axis_policy"],
                run["message_axis_policy"],
                _distribution_body(run["alpha_distribution"]),
                _distribution_body(run["theta_distribution"]),
                run["trial_count"],
                run["combo_count"],
                f'<a href="{escape(str(run["report_href"]))}">open</a>',
                _format_rate(run["accepted_rate"]),
                _format_rate(run["max_symbol_error_rate"]),
                _format_number(run["max_mean_abs_value_error"]),
                _format_number(run["max_required_tolerance_sigmas"]),
                _format_rate(run["max_check_failure_rate"]),
            ]
        )
    return _table(headers, rows, "table-wrap")


def _table(headers: list[str], rows: list[list[object]], class_name: str) -> str:
    header_html = "".join(f"<th>{escape(header)}</th>" for header in headers)
    row_html = "\n".join(
        "<tr>"
        + "".join(f"<td>{_html_cell(cell)}</td>" for cell in row)
        + "</tr>"
        for row in rows
    )
    return f"""
      <div class="{escape(class_name)}">
        <table>
          <thead><tr>{header_html}</tr></thead>
          <tbody>{row_html}</tbody>
        </table>
      </div>
    """


def _html_cell(value: object) -> str:
    text = str(value)
    if text.startswith("<a ") or text.startswith("<strong>"):
        return text
    return _text(value)


def _interval_rows(combos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for combo in combos:
        grouped.setdefault(str(combo["intervals"]), []).append(combo)
    return [
        _interval_row(intervals, grouped[intervals])
        for intervals in _unique_ordered(grouped)
    ]


def _interval_row(intervals: str, combos: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "intervals": intervals,
        "accepted_rate": _weighted_average(combos, "accepted_rate"),
        "symbol_error_rate": _weighted_average(combos, "symbol_error_rate"),
        "mean_abs_value_error": _weighted_average(combos, "mean_abs_value_error"),
        "required_acceptance_tolerance_sigmas_p95": _max_combo_metric(
            combos,
            "required_acceptance_tolerance_sigmas_p95",
        ),
    }


def _weighted_average(combos: list[dict[str, Any]], field: str) -> float | None:
    weighted_total = 0.0
    total_weight = 0.0
    for combo in combos:
        if combo.get(field) in ("", None):
            continue
        weight = float(combo.get("trial_count") or 1.0)
        weighted_total += float(combo[field]) * weight
        total_weight += weight
    return weighted_total / total_weight if total_weight else None


def _best_interval_row(
    rows: list[dict[str, Any]],
    field: str,
    selector,
) -> dict[str, Any] | None:
    values = [row for row in rows if row.get(field) is not None]
    if not values:
        return None
    selected_value = selector(float(row[field]) for row in values)
    for row in values:
        if float(row[field]) == selected_value:
            return row
    return None


def _metric_delta_against_default(
    rows: list[dict[str, Any]],
    field: str,
    selector,
) -> float | None:
    default_row = _default_interval_row(rows)
    best_row = _best_interval_row(rows, field, selector)
    if default_row is None or best_row is None:
        return None
    if default_row.get(field) is None or best_row.get(field) is None:
        return None
    return float(default_row[field]) - float(best_row[field])


def _delta_from_default(
    row: dict[str, Any],
    rows: list[dict[str, Any]],
    field: str,
) -> float | None:
    default_row = _default_interval_row(rows)
    if default_row is None or default_row.get(field) is None or row.get(field) is None:
        return None
    return float(default_row[field]) - float(row[field])


def _default_interval_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    for row in rows:
        if row.get("intervals") == "default":
            return row
    return None


def _max_combo_metric(
    combos: list[dict[str, Any]],
    field: str,
) -> float | None:
    values = [
        float(combo[field])
        for combo in combos
        if combo.get(field) not in ("", None)
    ]
    return max(values) if values else None


def _best_rate(runs: list[dict[str, Any]], field: str) -> str:
    values = [float(run[field]) for run in runs if run.get(field) is not None]
    if not values:
        return "n/a"
    return _format_rate(max(values))


def _best_symbol_delta(runs: list[dict[str, Any]]) -> str:
    values = [
        float(run["symbol_error_delta"])
        for run in runs
        if run.get("symbol_error_delta") is not None
    ]
    if not values:
        return "n/a"
    return _format_rate(max(values))


def _format_metric(metric: str, value: object) -> str:
    if metric.endswith("_rate"):
        return _format_rate(value)
    return _format_number(value)


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


def _format_signed_number(value: object) -> str:
    if value is None:
        return "n/a"
    number = float(value)
    if number == 0.0:
        return "0"
    sign = "+" if number > 0 else ""
    return f"{sign}{_format_number(number)}"


def _format_signed_rate(value: object) -> str:
    if value is None:
        return "n/a"
    number = float(value)
    if number == 0.0:
        return "0"
    sign = "+" if number > 0 else ""
    return f"{sign}{_format_rate(number)}"


def _format_run_id(value: object) -> str:
    if value is None:
        return "n/a"
    run_id = str(value)
    if run_id.startswith("run_"):
        return f"#{run_id.removeprefix('run_')}"
    return f"#{run_id}" if run_id.isdigit() else run_id


def _run_order(value: object) -> int:
    if value is None:
        return 0
    run_id = str(value).removeprefix("run_")
    return int(run_id) if run_id.isdigit() else 0


def _group_id(value: object) -> str:
    return "".join(
        character if character.isalnum() else "-"
        for character in str(value).lower()
    ).strip("-")


def _distribution_body(value: object) -> object:
    return value


def _text(value: object) -> str:
    if value is None:
        return "n/a"
    return escape(str(value))


def _unique_sorted(values) -> list:
    return sorted(set(values))


def _unique_ordered(values) -> list:
    ordered = []
    for value in values:
        if value not in ordered:
            ordered.append(value)
    return ordered


def _replace_placeholders(template: str, replacements: dict[str, object]) -> str:
    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace("{{ " + key + " }}", str(value))
    return rendered


if __name__ == "__main__":
    main()
