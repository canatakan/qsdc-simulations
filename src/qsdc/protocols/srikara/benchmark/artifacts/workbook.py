"""Excel workbook writer for benchmark summaries."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet


Row = list[object]

HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(color="FFFFFF", bold=True)


def write_benchmark_workbook(
    path: Path,
    summary: dict[str, Any],
    combos: list[dict[str, Any]],
    trials: list[dict[str, Any]],
) -> None:
    workbook = Workbook()
    workbook.remove(workbook.active)

    _add_sheet(workbook, "Run", _run_rows(summary), freeze_header=False)
    _add_sheet(workbook, "Overview", _overview_rows(combos))
    _add_sheet(workbook, "Errors", _error_rows(combos))
    _add_sheet(workbook, "Checks", _check_rows(combos))
    _add_sheet(workbook, "Tolerance", _tolerance_rows(combos))
    _add_sheet(workbook, "Trial Tolerance", _trial_tolerance_rows(trials))

    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)


def _add_sheet(
    workbook: Workbook,
    title: str,
    rows: Iterable[Row],
    freeze_header: bool = True,
) -> Worksheet:
    sheet = workbook.create_sheet(title=title)
    for row in rows:
        sheet.append(row)
    if freeze_header:
        _style_table_sheet(sheet)
    else:
        _style_run_sheet(sheet)
    _resize_columns(sheet)
    return sheet


def _style_table_sheet(sheet: Worksheet) -> None:
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for cell in sheet[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center")
    _format_data_cells(sheet)


def _style_run_sheet(sheet: Worksheet) -> None:
    sheet.freeze_panes = "A2"
    for cell in sheet[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
    for row_index in (1, 12):
        for cell in sheet[row_index]:
            if cell.value is not None:
                cell.font = HEADER_FONT
                cell.fill = HEADER_FILL
    for row in sheet.iter_rows(min_row=2, max_col=2):
        row[1].number_format = _number_format_for_header(str(row[0].value))


def _resize_columns(sheet: Worksheet) -> None:
    for column_cells in sheet.columns:
        width = max(
            len(str(cell.value)) if cell.value is not None else 0
            for cell in column_cells
        )
        column_letter = get_column_letter(column_cells[0].column)
        sheet.column_dimensions[column_letter].width = min(max(width + 2, 10), 42)


def _format_data_cells(sheet: Worksheet) -> None:
    headers = [str(cell.value) for cell in sheet[1]]
    for column_index, header in enumerate(headers, start=1):
        number_format = _number_format_for_header(header)
        for cell in sheet.iter_cols(
            min_col=column_index,
            max_col=column_index,
            min_row=2,
            max_row=sheet.max_row,
        ):
            for data_cell in cell:
                data_cell.number_format = number_format


def _number_format_for_header(header: str) -> str:
    if header.endswith("_count") or header.endswith("_index"):
        return "0"
    if header.endswith("_rate") or header == "one_probability":
        return "0.0000"
    if "sigma" in header or "tolerance" in header:
        return "0.000000"
    if "error" in header or "margin" in header or header.endswith("_seconds"):
        return "0.000000"
    return "General"


def _run_rows(summary: dict[str, Any]) -> list[Row]:
    rows: list[Row] = [
        ["Run Metric", "Value"],
        ["name", summary.get("name")],
        ["benchmark_run_id", summary.get("benchmark_run_id")],
        ["benchmark_run_unix_seconds", summary.get("benchmark_run_unix_seconds")],
        ["output_dir", summary.get("output_dir")],
        ["combo_count", summary.get("combo_count")],
        ["trial_count", summary.get("trial_count")],
        ["accepted_count", summary.get("accepted_count")],
        ["accepted_rate", summary.get("accepted_rate")],
        ["elapsed_seconds", summary.get("elapsed_seconds")],
        [],
        ["Derived Count", "Value"],
    ]
    derived_counts = summary.get("derived_counts", {})
    if isinstance(derived_counts, dict):
        for key, value in derived_counts.items():
            rows.append([key, value])
    return rows


def _overview_rows(combos: list[dict[str, Any]]) -> list[Row]:
    rows = [
        [
            "combo_index",
            "one_probability",
            "r_distribution",
            "trial_count",
            "accepted_count",
            "accepted_rate",
            "control_pass_rate",
            "decoy_pass_rate",
        ]
    ]
    for combo in combos:
        rows.append(
            [
                combo["combo_index"],
                combo["one_probability"],
                combo["r_distribution"],
                combo["trial_count"],
                combo["accepted_count"],
                combo["accepted_rate"],
                combo["control_pass_rate"],
                combo["decoy_pass_rate"],
            ]
        )
    return rows


def _error_rows(combos: list[dict[str, Any]]) -> list[Row]:
    rows = [
        [
            "combo_index",
            "one_probability",
            "r_distribution",
            "all_bit_error_rate",
            "all_symbol_error_rate",
            "all_mean_abs_value_error",
            "all_mean_interval_margin",
            "accepted_bit_error_rate",
            "accepted_symbol_error_rate",
            "rejected_bit_error_rate",
            "rejected_symbol_error_rate",
        ]
    ]
    for combo in combos:
        rows.append(
            [
                combo["combo_index"],
                combo["one_probability"],
                combo["r_distribution"],
                combo["all"]["bit_error_rate"],
                combo["all"]["symbol_error_rate"],
                combo["all"]["mean_abs_value_error"],
                combo["all"]["mean_interval_margin"],
                combo["accepted"]["bit_error_rate"],
                combo["accepted"]["symbol_error_rate"],
                combo["rejected"]["bit_error_rate"],
                combo["rejected"]["symbol_error_rate"],
            ]
        )
    return rows


def _check_rows(combos: list[dict[str, Any]]) -> list[Row]:
    rows = [
        [
            "combo_index",
            "one_probability",
            "r_distribution",
            "control_check_count",
            "control_failed_check_count",
            "control_failed_check_rate",
            "control_mean_failed_check_count_per_trial",
            "control_max_failed_check_count_per_trial",
            "decoy_check_count",
            "decoy_failed_check_count",
            "decoy_failed_check_rate",
            "decoy_mean_failed_check_count_per_trial",
            "decoy_max_failed_check_count_per_trial",
        ]
    ]
    for combo in combos:
        rows.append(
            [
                combo["combo_index"],
                combo["one_probability"],
                combo["r_distribution"],
                combo["control_check_count"],
                combo["control_failed_check_count"],
                combo["control_failed_check_rate"],
                combo["control_mean_failed_check_count_per_trial"],
                combo["control_max_failed_check_count_per_trial"],
                combo["decoy_check_count"],
                combo["decoy_failed_check_count"],
                combo["decoy_failed_check_rate"],
                combo["decoy_mean_failed_check_count_per_trial"],
                combo["decoy_max_failed_check_count_per_trial"],
            ]
        )
    return rows


def _tolerance_rows(combos: list[dict[str, Any]]) -> list[Row]:
    rows = [
        [
            "combo_index",
            "one_probability",
            "r_distribution",
            "check_tolerance_sigmas",
            "measurement_noise_sigma",
            "required_acceptance_tolerance_sigmas_min",
            "required_acceptance_tolerance_sigmas_mean",
            "required_acceptance_tolerance_sigmas_median",
            "required_acceptance_tolerance_sigmas_p95",
            "required_acceptance_tolerance_sigmas_max",
        ]
    ]
    for combo in combos:
        thresholds = combo["all"]["required_acceptance_tolerance_sigmas"]
        rows.append(
            [
                combo["combo_index"],
                combo["one_probability"],
                combo["r_distribution"],
                combo["check_tolerance_sigmas"],
                combo["measurement_noise_sigma"],
                thresholds["min"],
                thresholds["mean"],
                thresholds["median"],
                thresholds["p95"],
                thresholds["max"],
            ]
        )
    return rows


def _trial_tolerance_rows(trials: list[dict[str, Any]]) -> list[Row]:
    rows = [
        [
            "combo_index",
            "trial_index",
            "one_probability",
            "r_distribution",
            "accepted",
            "control_passed",
            "decoy_passed",
            "control_failed_check_count",
            "decoy_failed_check_count",
            "required_control_tolerance_sigmas",
            "required_decoy_tolerance_sigmas",
            "required_acceptance_tolerance_sigmas",
        ]
    ]
    for trial in trials:
        rows.append(
            [
                trial["combo_index"],
                trial["trial_index"],
                trial["one_probability"],
                trial["r_distribution"],
                trial["accepted"],
                trial["control_passed"],
                trial["decoy_passed"],
                trial["control_failed_check_count"],
                trial["decoy_failed_check_count"],
                trial["required_control_tolerance_sigmas"],
                trial["required_decoy_tolerance_sigmas"],
                trial["required_acceptance_tolerance_sigmas"],
            ]
        )
    return rows
