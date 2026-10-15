from __future__ import annotations

from itertools import product

import yaml

from ..benchmark import Benchmark, Case, Workload
from ..suite import Suite


def assign(document: dict, path: str, value: object) -> None:
    *parents, key = path.split(".")
    for parent in parents:
        document = document[parent]

    document[key] = value


class Catalog:
    def __init__(self, suite: Suite):
        self.suite = suite
        self.specs = yaml.safe_load(suite.studies.read_text())
        self.groups = self.specs["groups"]
        self.study_groups = {
            name: spec["group"] for name, spec in self.specs["studies"].items()
        }

    @property
    def names(self) -> list[str]:
        return list(self.specs["studies"])

    def study_order(self, name: str) -> tuple[int, int]:
        groups = list(self.groups)
        group = self.study_groups.get(name)
        names = list(self.study_groups)

        return (
            groups.index(group) if group in groups else len(groups),
            names.index(name) if name in names else len(names),
        )

    def studies(self, workload: Workload) -> list[Benchmark]:
        return [
            self.study(name, spec, workload)
            for name, spec in self.specs["studies"].items()
        ]

    def study(self, name: str, spec: dict, workload: Workload) -> Benchmark:
        axes = spec.get("axes", [])
        points = spec.get("cases") or [
            {
                "set": {path: v for axis, v in zip(axes, at) for path in axis["set"]},
                "at": at,
            }
            for at in product(*(axis["values"] for axis in axes))
        ]

        simulator = spec.get("simulator", self.specs["simulator"])
        shared = spec.get("set", {})

        cases = [
            self.case(point, shared, simulator, noise, workload)
            for noise in spec.get("noise", self.specs["noise"])
            for point in points
        ]

        return Benchmark(
            self.suite, name, tuple(cases), tuple(axis["name"] for axis in axes)
        )

    def case(
        self, spec: dict, shared: dict, simulator: str, noise: str, workload: Workload
    ) -> Case:
        suite = self.suite
        preset = spec.get("simulator", simulator)
        if isinstance(preset, dict):
            preset = preset.get(noise, preset["default"])

        document = suite.presets[preset].model_dump()
        document["noise"] = suite.noises[noise].model_dump()
        document["workload"] = workload.model_dump()

        for path, value in {**shared, **spec.get("set", {})}.items():
            assign(document, path, value)

        payload = Workload.model_validate(document.pop("workload"))

        label = spec.get("label")
        if isinstance(label, dict):
            label = label.get(noise, label["default"])

        return Case(
            suite.config.model_validate(document),
            payload,
            series=noise,
            label=label,
            at=tuple(spec.get("at", ())),
        )
