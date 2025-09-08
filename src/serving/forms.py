from enum import Enum
from typing import Any
from bevy import Inject, auto_inject, injectable
from starlette.requests import Request
from starlette.templating import Jinja2Templates
from markupsafe import Markup

from serving.auth import CredentialProvider


class CSRFProtection(Enum):
    Enabled = "enabled"
    Disabled = "disabled"


class MissingCSRFTokenError(RuntimeError):
    """Raised when a form template fails to render a CSRF token."""


class Form:
    __form_options__: dict[str, Any]

    def __init_subclass__(
        cls, *, template: str, csrf: CSRFProtection = CSRFProtection.Enabled, **kwargs
    ):
        super().__init_subclass__(**kwargs)
        cls.__form_options__ = {"template": template, "csrf": csrf}

    @auto_inject
    @injectable
    def render(
        self,
        templates: Inject[Jinja2Templates],
        credential_provider: Inject[CredentialProvider],
    ) -> str:
        options = self.__form_options__
        context: dict[str, Any] = {"form": self}

        if options["csrf"] is CSRFProtection.Enabled:
            token = credential_provider.generate_csrf_token()
            called = False

            def csrf() -> Markup:
                nonlocal called
                called = True
                return Markup(
                    f'<input type="hidden" name="csrf_token" value="{token}">'  # noqa: B907
                )

            context["csrf"] = csrf

            template = templates.get_template(options["template"])
            result = template.render(context)
            if not called:
                raise MissingCSRFTokenError(
                    "CSRF token was not injected; call csrf() in the form template"
                )
            return result

        return templates.get_template(options["template"]).render(context)

    @classmethod
    @auto_inject
    @injectable
    async def from_request[T: "Form"](
        cls: type[T],
        request: Inject[Request],
        credential_provider: Inject[CredentialProvider],
    ) -> T:
        form = await request.form()
        options = cls.__form_options__
        if options["csrf"] is CSRFProtection.Enabled:
            token = form.get("csrf_token")
            if not token or not credential_provider.validate_csrf_token(token):
                raise ValueError("Invalid CSRF token")
        data = {k: form.get(k) for k in cls.__annotations__.keys() if k in form}
        return cls(**data)
