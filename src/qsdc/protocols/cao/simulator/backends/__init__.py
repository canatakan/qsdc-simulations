"""Backend constructors for the Cao simulator."""

from __future__ import annotations

from qsdc.protocols.cao.simulator.backends.analytic.ideal import AnalyticBackend
from qsdc.protocols.cao.simulator.backends.base import GaussianMappingBackend


def make_backend(name: str) -> GaussianMappingBackend:
    if name == "analytic":
        return AnalyticBackend()
    raise ValueError(f"unknown backend {name!r}")


__all__ = ["AnalyticBackend", "GaussianMappingBackend", "make_backend"]
