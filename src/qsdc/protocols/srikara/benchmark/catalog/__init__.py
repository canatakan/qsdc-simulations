from __future__ import annotations

from itertools import product
from pathlib import Path

import yaml

from qsdc.common.config.noise import BASELINES

from ...config import NoiseConfig, SimulatorConfig
from ..benchmark import Benchmark, Case, Workload


def load(name: str) -> dict:
    return yaml.safe_load((Path(__file__).parent / f"{name}.yaml").read_text())


def resolve(name: str, specs: dict) -> dict:
    spec = dict(specs[name])
    parent = spec.pop("extends", None)

    return {**resolve(parent, specs), **spec} if parent else spec


def assign(document: dict, path: str, value: object) -> None:
    *parents, key = path.split(".")
    for parent in parents:
        document = document[parent]

    document[key] = value


NOISES = {
    name: NoiseConfig.from_environment(environment)
    for name, environment in BASELINES.items()
}

SIMULATOR_SPECS = load("simulators")
SIMULATORS = {
    name: SimulatorConfig.model_validate(resolve(name, SIMULATOR_SPECS))
    for name in SIMULATOR_SPECS
}

STUDY_SPECS = load("studies")
GROUPS = STUDY_SPECS["groups"]
STUDY_GROUPS = {name: spec["group"] for name, spec in STUDY_SPECS["studies"].items()}


def study_order(name: str) -> tuple[int, int]:
    # A study's place in the catalog: its group, then the study itself. Unknown
    # names go last.
    groups = list(GROUPS)
    group = STUDY_GROUPS.get(name)
    names = list(STUDY_GROUPS)

    return (
        groups.index(group) if group in groups else len(groups),
        names.index(name) if name in names else len(names),
    )


def studies(workload: Workload) -> list[Benchmark]:
    return [
        study(name, spec, workload) for name, spec in STUDY_SPECS["studies"].items()
    ]


def study(name: str, spec: dict, workload: Workload) -> Benchmark:
    axes = spec.get("axes", [])
    points = spec.get("cases") or [
        {
            "set": {path: v for axis, v in zip(axes, at) for path in axis["set"]},
            "at": at,
        }
        for at in product(*(axis["values"] for axis in axes))
    ]

    simulator = spec.get("simulator", STUDY_SPECS["simulator"])
    shared = spec.get("set", {})

    cases = [
        case(point, shared, simulator, noise, workload)
        for noise in spec.get("noise", STUDY_SPECS["noise"])
        for point in points
    ]

    return Benchmark(name, tuple(cases), tuple(axis["name"] for axis in axes))


def case(
    spec: dict, shared: dict, simulator: str, noise: str, workload: Workload
) -> Case:
    document = SIMULATORS[spec.get("simulator", simulator)].model_dump()
    document["noise"] = NOISES[noise].model_dump()
    document["workload"] = workload.model_dump()

    for path, value in {**shared, **spec.get("set", {})}.items():
        assign(document, path, value)

    payload = Workload.model_validate(document.pop("workload"))

    return Case(
        SimulatorConfig.model_validate(document),
        payload,
        series=noise,
        label=spec.get("label"),
        at=tuple(spec.get("at", ())),
    )
