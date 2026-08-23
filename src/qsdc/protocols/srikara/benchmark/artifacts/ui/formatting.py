"""Format benchmark values for display in the static UI."""

from __future__ import annotations

from qsdc.protocols.srikara.configuration.distribution import Distribution
from qsdc.protocols.srikara.configuration.noise import NoiseConfig


def rate(value: object) -> str:
    if value is None:
        return "n/a"
    return f"{100.0 * float(value):.2f}%"


def number(value: object) -> str:
    if value is None:
        return "n/a"
    numeric_value = float(value)
    if numeric_value == 0.0:
        return "0"
    if abs(numeric_value) < 1e-4 or abs(numeric_value) >= 1e5:
        return f"{numeric_value:.6e}"
    return f"{numeric_value:.6g}"


def run_id(value: object) -> str:
    if value is None:
        return "n/a"
    identifier = str(value)
    if identifier.startswith("run_"):
        return f"#{identifier.removeprefix('run_')}"
    return f"#{identifier}" if identifier.isdigit() else identifier


def text(value: object) -> str:
    return "n/a" if value is None else str(value)


def distribution_summary(value: Distribution) -> str:
    return value.summary()


def noise_summary(value: NoiseConfig) -> str:
    configured = [
        f"{name.replace('_', ' ')}: {', '.join(effect.type for effect in effects)}"
        for name in type(value).model_fields
        if (effects := getattr(value, name))
    ]
    return "; ".join(configured) if configured else "none"


def plot_title(value: object) -> str:
    return str(value).rsplit("/", 1)[-1].removesuffix(".png").replace("_", " ")


def metric(name: str, value: object) -> str:
    return rate(value) if name.endswith("_rate") else number(value)


def table_cell(header: str, value: object) -> str:
    if value is None:
        return "n/a"
    if _is_identifier_field(header):
        return _identifier(value)
    if header.endswith("_rate"):
        return rate(value)
    if isinstance(value, bool):
        return "yes" if value else "no"
    if _looks_numeric(value):
        return number(value)
    return text(value)


def human_header(header: str) -> str:
    replacements = {
        "r_distribution": "r",
        "one_probability": "one probability",
        "mean_abs_value_error": "mean absolute numeric error",
    }
    return replacements.get(header, header.replace("_", " "))


def compact_distribution(value: object) -> str:
    label = str(value)
    if label.lower().startswith("r="):
        label = label[2:]
    if label.startswith("fixed(value=") and label.endswith(")"):
        body = label.removeprefix("fixed(value=").removesuffix(")")
        return f"fixed[{body}]"
    if label.startswith("uniform(lower=") and label.endswith(")"):
        body = label.removeprefix("uniform(lower=").removesuffix(")")
        return f"uniform[{body.replace(', upper=', ', ')}]"
    return label


def distribution(value: object, parameter: str) -> str:
    """Remove a redundant parameter prefix from a distribution summary."""
    label = text(value)
    prefix = f"{parameter}="
    return label.removeprefix(prefix)


def count(count_value: int, noun: str) -> str:
    suffix = "" if count_value == 1 else "s"
    return f"{count_value} {noun}{suffix}"


def html_id(value: object) -> str:
    return "".join(
        character if character.isalnum() else "-"
        for character in str(value).lower()
    ).strip("-")


def _is_identifier_field(header: str) -> bool:
    return header.endswith(("_seed", "_index", "_count"))


def _identifier(value: object) -> str:
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return text(value)
    if numeric_value.is_integer():
        return str(int(numeric_value))
    return text(value)


def _looks_numeric(value: object) -> bool:
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True
