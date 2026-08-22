"""Shared rendering helpers for the static benchmark UI."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from jinja2 import BaseLoader, Environment, StrictUndefined, TemplateNotFound

from qsdc.protocols.srikara.benchmark.artifacts.ui.utils.formatting import (
    distribution_summary,
    noise_summary,
    number,
    plot_title,
    rate,
    run_id,
    text,
)

_TEMPLATE_DIRECTORY = "templates"


class _PackageTemplateLoader(BaseLoader):
    """Load Jinja templates from this installable Python package."""

    def get_source(self, environment: Environment, template: str):
        del environment
        resource = _resource(_TEMPLATE_DIRECTORY, template)
        if not resource.is_file():
            raise TemplateNotFound(template)
        source = resource.read_text(encoding="utf-8")
        return source, str(resource), lambda: True


_environment = Environment(
    loader=_PackageTemplateLoader(),
    autoescape=True,
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)
_environment.filters.update(
    distribution_summary=distribution_summary,
    noise_summary=noise_summary,
    number=number,
    plot_title=plot_title,
    rate=rate,
    run_id=run_id,
    text=text,
)


def render_template(template_name: str, **context: object) -> str:
    """Render a packaged HTML template with automatic escaping enabled."""
    return _environment.get_template(template_name).render(**context)


def copy_asset(name: str, destination: str | Path) -> None:
    """Copy a packaged UI asset to a generated artifact directory."""
    Path(destination).write_bytes(_resource("static", name).read_bytes())


def _resource(*parts: str):
    resource = files(__package__)
    for part in parts:
        for path_part in part.split("/"):
            if not path_part or path_part in {".", ".."}:
                raise ValueError(f"Invalid UI resource path: {part}")
            resource = resource.joinpath(path_part)
    return resource
