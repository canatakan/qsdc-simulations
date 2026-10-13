from __future__ import annotations

from pathlib import Path
from typing import TypeVar

import yaml

from .base import Config

ConfigT = TypeVar("ConfigT", bound=Config)


def load_presets(path: Path, config: type[ConfigT]) -> dict[str, ConfigT]:
    # Named configurations. A preset may extend another and change its fields.
    specs = yaml.safe_load(path.read_text())

    return {name: config.model_validate(_resolve(name, specs)) for name in specs}


def _resolve(name: str, specs: dict) -> dict:
    spec = dict(specs[name])
    parent = spec.pop("extends", None)

    return {**_resolve(parent, specs), **spec} if parent else spec
