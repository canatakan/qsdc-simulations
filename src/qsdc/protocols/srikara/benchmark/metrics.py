"""Metric helpers for benchmark trial and combo summaries."""

from __future__ import annotations

from math import ceil
from statistics import mean
from typing import Iterable, Sequence

from qsdc.common.bits import hamming_distance
from qsdc.protocols.srikara.simulator.encoding import interval_for_bits
from qsdc.protocols.srikara.simulator.protocol import ControlCheck, DecoyCheck, MessageDecode


def summarize_messages(
    messages: Sequence[MessageDecode],
    payload_bit_count: int | None = None,
) -> dict[str, float | int]:
    sent_transmitted_bits = "".join(message.sent_bits for message in messages)
    decoded_transmitted_bits = "".join(message.decoded_bits for message in messages)
    if payload_bit_count is None:
        payload_bit_count = len(sent_transmitted_bits)
    if payload_bit_count < 0 or payload_bit_count > len(sent_transmitted_bits):
        raise ValueError("payload_bit_count is outside the transmitted bitstream")

    sent_payload_bits = sent_transmitted_bits[:payload_bit_count]
    decoded_payload_bits = decoded_transmitted_bits[:payload_bit_count]
    bit_error_count = hamming_distance(sent_payload_bits, decoded_payload_bits)
    symbol_error_count = sum(
        1 for message in messages if message.sent_bits != message.decoded_bits
    )
    padding_bit_count = len(sent_transmitted_bits) - payload_bit_count
    symbol_count = len(messages)

    absolute_errors: list[float] = []
    miss_distances: list[float] = []
    margins: list[float] = []
    for message in messages:
        absolute_errors.append(abs(message.decoded_value - message.message_value))
        miss_distance, margin = interval_position(
            message.sent_bits,
            message.decoded_value,
        )
        miss_distances.append(miss_distance)
        margins.append(margin)

    return {
        "payload_bit_count": payload_bit_count,
        "padding_bit_count": padding_bit_count,
        "transmitted_message_bit_count": len(sent_transmitted_bits),
        "message_bit_count": payload_bit_count,
        "message_bit_error_count": bit_error_count,
        "bit_error_rate": (
            bit_error_count / payload_bit_count if payload_bit_count else 0.0
        ),
        "message_symbol_count": symbol_count,
        "message_mode_count": symbol_count,
        "message_symbol_error_count": symbol_error_count,
        "symbol_error_rate": (
            symbol_error_count / symbol_count if symbol_count else 0.0
        ),
        "mean_abs_value_error": _mean_or_zero(absolute_errors),
        "max_abs_value_error": max(absolute_errors, default=0.0),
        "mean_interval_miss_distance": _mean_or_zero(miss_distances),
        "max_interval_miss_distance": max(miss_distances, default=0.0),
        "mean_interval_margin": _mean_or_zero(margins),
        "min_interval_margin": min(margins, default=0.0),
    }


def interval_position(bits: str, decoded_value: float) -> tuple[float, float]:
    interval = interval_for_bits(bits)
    if interval.contains(decoded_value):
        if interval.lower == float("-inf"):
            margin = interval.upper - decoded_value
        elif interval.upper == float("inf"):
            margin = decoded_value - interval.lower
        else:
            margin = min(decoded_value - interval.lower, interval.upper - decoded_value)
        return 0.0, margin
    if decoded_value <= interval.lower:
        miss_distance = interval.lower - decoded_value
    elif decoded_value >= interval.upper:
        miss_distance = decoded_value - interval.upper
    else:
        miss_distance = 0.0
    return miss_distance, -miss_distance


def summarize_checks(
    checks: Sequence[ControlCheck] | Sequence[DecoyCheck],
) -> dict[str, float | int | bool]:
    deviations = [abs(check.measured - check.expected) for check in checks]
    failed = sum(1 for check in checks if not check.passed)
    return {
        "check_count": len(checks),
        "failed_check_count": failed,
        "passed": failed == 0,
        "mean_abs_deviation": _mean_or_zero(deviations),
        "max_abs_deviation": max(deviations, default=0.0),
    }


def aggregate_trial_metrics(
    trials: Sequence[dict[str, object]],
    accepted: bool | None = None,
) -> dict[str, object]:
    selected = [
        trial
        for trial in trials
        if accepted is None or bool(trial["accepted"]) is accepted
    ]
    if not selected:
        return {
            "trial_count": 0,
            "bit_error_rate": None,
            "symbol_error_rate": None,
            "mean_abs_value_error": None,
            "mean_interval_miss_distance": None,
            "mean_interval_margin": None,
            "required_acceptance_tolerance_sigmas": {
                "min": None,
                "mean": None,
                "median": None,
                "p95": None,
                "max": None,
            },
        }

    bit_errors = sum(int(trial["message_bit_error_count"]) for trial in selected)
    bit_count = sum(int(trial["message_bit_count"]) for trial in selected)
    symbol_errors = sum(int(trial["message_symbol_error_count"]) for trial in selected)
    symbol_count = sum(int(trial["message_symbol_count"]) for trial in selected)
    return {
        "trial_count": len(selected),
        "bit_error_rate": bit_errors / bit_count if bit_count else 0.0,
        "symbol_error_rate": symbol_errors / symbol_count if symbol_count else 0.0,
        "mean_abs_value_error": _mean_trial_field(
            selected,
            "mean_abs_value_error",
        ),
        "mean_interval_miss_distance": _mean_trial_field(
            selected,
            "mean_interval_miss_distance",
        ),
        "mean_interval_margin": _mean_trial_field(selected, "mean_interval_margin"),
        "required_acceptance_tolerance_sigmas": _threshold_summary(
            float(trial["required_acceptance_tolerance_sigmas"])
            for trial in selected
        ),
    }


def _mean_trial_field(trials: Sequence[dict[str, object]], field: str) -> float:
    return mean(float(trial[field]) for trial in trials)


def _mean_or_zero(values: Iterable[float]) -> float:
    values = tuple(values)
    return mean(values) if values else 0.0


def _threshold_summary(values: Iterable[float]) -> dict[str, float | None]:
    sorted_values = sorted(values)
    if not sorted_values:
        return {
            "min": None,
            "mean": None,
            "median": None,
            "p95": None,
            "max": None,
        }
    middle = len(sorted_values) // 2
    if len(sorted_values) % 2:
        median = sorted_values[middle]
    else:
        median = (sorted_values[middle - 1] + sorted_values[middle]) / 2
    p95_index = max(ceil(0.95 * len(sorted_values)) - 1, 0)
    return {
        "min": sorted_values[0],
        "mean": mean(sorted_values),
        "median": median,
        "p95": sorted_values[p95_index],
        "max": sorted_values[-1],
    }
