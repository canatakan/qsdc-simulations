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
            str(run["intervals"]),
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
    return {
        "name": summary.get("name"),
        "run_id": summary.get("benchmark_run_id"),
        "backend": parameters.get("backend"),
        "intervals": parameters.get("intervals", "default"),
        "check_axis_policy": parameters.get("check_axis_policy"),
        "message_axis_policy": parameters.get("message_axis_policy"),
        "alpha_distribution": parameters.get("alpha_distribution"),
        "theta_distribution": parameters.get("theta_distribution"),
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
    template = read_template("index.html")
    replacements = {
        "title": _text(f"Srikara benchmark UI: {root.name}"),
        "heading": _text(root.name),
        "run_count": len(runs),
        "cards": _cards(runs),
        "run_table": _run_table(runs),
    }
    return _replace_placeholders(template, replacements)


def _cards(runs: list[dict[str, Any]]) -> str:
    return "\n".join(
        [
            _card("Runs", len(runs), "benchmark reports found"),
            _card(
                "Best accepted trials",
                _best_rate(runs, "accepted_rate"),
                "highest accepted-trial rate",
            ),
            _card(
                "Worst symbol error",
                _best_rate(runs, "max_symbol_error_rate"),
                "largest per-run symbol error",
            ),
            _card(
                "Worst numeric error",
                _best_number(runs, "max_mean_abs_value_error"),
                "largest per-run mean numeric error",
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


def _run_table(runs: list[dict[str, Any]]) -> str:
    headers = [
        "name",
        "run",
        "backend",
        "intervals",
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
                run["intervals"],
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
    header_html = "".join(f"<th>{escape(header)}</th>" for header in headers)
    row_html = "\n".join(
        "<tr>"
        + "".join(
            f"<td>{cell if str(cell).startswith('<a ') else _text(cell)}</td>"
            for cell in row
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


def _best_number(runs: list[dict[str, Any]], field: str) -> str:
    values = [float(run[field]) for run in runs if run.get(field) is not None]
    if not values:
        return "n/a"
    return _format_number(max(values))


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
    if not isinstance(value, str):
        return value
    _, separator, body = value.partition("=")
    return body if separator else value


def _text(value: object) -> str:
    if value is None:
        return "n/a"
    return escape(str(value))


def _replace_placeholders(template: str, replacements: dict[str, object]) -> str:
    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace("{{ " + key + " }}", str(value))
    return rendered


if __name__ == "__main__":
    main()
