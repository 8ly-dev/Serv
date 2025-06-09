"""Additional response types for Serv applications."""

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from ..extensions import Listener
from .response_utils import BaseResponse as Response


class Jinja2Response(Response):
    """Response that renders Jinja2 templates."""

    def __init__(
        self,
        template: str,
        context: dict[str, Any] | None = None,
        status_code: int = 200,
    ):
        super().__init__(status_code)
        self.template = template
        self.context = context or {}

    async def render(self) -> AsyncGenerator[bytes]:
        import jinja2

        template_dirs = self._get_template_locations(self.created_by)
        # Ensure template_dirs is a list (handle test override case)
        if not isinstance(template_dirs, list):
            template_dirs = [template_dirs]

        for template_dir in template_dirs:
            if template_dir.exists():
                loader = jinja2.FileSystemLoader(template_dir)
                env = jinja2.Environment(loader=loader)
                try:
                    template = env.get_template(self.template)
                    html = template.render(**self.context)
                    yield html.encode("utf-8")
                    return
                except jinja2.TemplateNotFound:
                    continue

        raise FileNotFoundError(
            f"Template '{self.template}' not found in any of the template directories: {template_dirs}"
        )

    @staticmethod
    def _get_template_locations(extension: Listener | None):
        if not extension:
            raise RuntimeError("Jinja2Response cannot be used outside of a extension.")

        return [
            Path.cwd() / "templates" / extension.name,
            extension.path / "templates",
        ]

    def __repr__(self):
        return (
            f"<{self.__class__.__name__}"
            f" status={self.status_code}"
            f" headers={self.headers}"
            f" template={self.template!r}"
            f" context={self.context!r}"
            f">"
        )
