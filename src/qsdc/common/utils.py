from __future__ import annotations

from math import inf


def header(title: str) -> None:
    print(f"\n{title}\n{'=' * len(title)}")


def step(title: str) -> None:
    print(f"\n{title}\n{'-' * len(title)}")


def table(
    headers: tuple[str, ...], rows: list[tuple[object, ...]], indent: str = ""
) -> None:
    cells = [tuple(str(cell) for cell in row) for row in rows]
    widths = [
        max(len(h), *(len(row[i]) for row in cells)) for i, h in enumerate(headers)
    ]
    for row in (headers, tuple("-" * w for w in widths), *cells):
        print(
            (indent + "  ".join(cell.ljust(w) for cell, w in zip(row, widths))).rstrip()
        )


def interval(lower: float, upper: float) -> str:
    left = "-inf" if lower == -inf else f"{lower:.4g}"
    right = "inf" if upper == inf else f"{upper:.4g}"
    return f"[{left}, {right})"
