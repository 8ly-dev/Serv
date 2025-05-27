import json
import sys
from collections import defaultdict
from collections.abc import AsyncGenerator
from datetime import date, datetime
from inspect import get_annotations, signature
from pathlib import Path
from types import NoneType, UnionType
from typing import (
    Annotated,
    Any,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from bevy import dependency, inject
from bevy.containers import Container

import serv
import serv.plugins.loader as pl
from serv.exceptions import HTTPMethodNotAllowedException
from serv.plugins import Plugin
from serv.requests import Request
from serv.responses import ResponseBuilder


class Response:
    def __init__(
        self,
        status_code: int,
        body: str | bytes | None = None,
        headers: dict[str, str] | None = None,
    ):
        self.status_code = status_code
        self.body = body or b""
        self.headers = headers or {}

        # A reference to the handler that returned this response. This is only set after creation but
        # before the response is rendered.
        self.created_by = None

    async def render(self) -> AsyncGenerator[bytes]:
        yield self.body

    def set_created_by(self, handler: Any) -> None:
        self.created_by = handler


class JsonResponse(Response):
    def __init__(self, data: Any, status_code: int = 200):
        super().__init__(status_code)
        self.body = json.dumps(data)
        self.headers["Content-Type"] = "application/json"


class TextResponse(Response):
    def __init__(self, text: str, status_code: int = 200):
        super().__init__(status_code)
        self.body = text
        self.headers["Content-Type"] = "text/plain"


class HtmlResponse(Response):
    def __init__(self, html: str, status_code: int = 200):
        super().__init__(status_code)
        self.body = html
        self.headers["Content-Type"] = "text/html"


class FileResponse(Response):
    def __init__(
        self,
        file: bytes,
        filename: str,
        status_code: int = 200,
        content_type: str = "application/octet-stream",
    ):
        super().__init__(status_code)
        self.body = file
        self.headers["Content-Type"] = content_type
        self.headers["Content-Disposition"] = f"attachment; filename={filename}"


class StreamingResponse(Response):
    def __init__(
        self,
        content: AsyncGenerator[str | bytes],
        status_code: int = 200,
        media_type: str = "text/plain",
        headers: dict[str, str] | None = None,
    ):
        super().__init__(status_code, headers=headers)
        self.content = content
        self.headers["Content-Type"] = media_type

    async def render(self) -> AsyncGenerator[bytes]:
        async for chunk in self.content:
            if isinstance(chunk, str):
                yield chunk.encode("utf-8")
            elif isinstance(chunk, bytes):
                yield chunk
            else:
                yield str(chunk).encode("utf-8")


class ServerSentEventsResponse(StreamingResponse):
    def __init__(
        self,
        content: AsyncGenerator[str | bytes],
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ):
        sse_headers = {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
        if headers:
            sse_headers.update(headers)

        super().__init__(content, status_code, "text/event-stream", sse_headers)


class RedirectResponse(Response):
    def __init__(self, url: str, status_code: int = 302):
        super().__init__(status_code)
        self.headers["Location"] = url
        self.body = f"Redirecting to {url}"


class Jinja2Response(Response):
    def __init__(self, template: str, context: dict[str, Any], status_code: int = 200):
        super().__init__(status_code)
        self.template = template
        self.context = context
        self.headers["Content-Type"] = "text/html"

    def render(self) -> AsyncGenerator[str, object]:
        from jinja2 import Environment, FileSystemLoader

        template_locations = self._get_template_locations(self.created_by)

        env = Environment(
            loader=FileSystemLoader(template_locations), enable_async=True
        )
        template = env.get_template(self.template)
        return template.generate_async(**self.context)

    @staticmethod
    def _get_template_locations(plugin: "pl.PluginSpec"):
        if not plugin:
            raise RuntimeError("Jinja2Response cannot be used outside of a plugin.")

        return [
            Path.cwd() / "templates" / plugin.name,
            plugin.path / "templates",
        ]


class GetRequest(Request):
    pass


class PostRequest(Request):
    pass


class PutRequest(Request):
    pass


class DeleteRequest(Request):
    pass


class PatchRequest(Request):
    pass


class OptionsRequest(Request):
    pass


class HeadRequest(Request):
    pass


MethodMapping = {
    GetRequest: "GET",
    PostRequest: "POST",
    PutRequest: "PUT",
    DeleteRequest: "DELETE",
    PatchRequest: "PATCH",
    OptionsRequest: "OPTIONS",
    HeadRequest: "HEAD",
}


def normalized_origin(annotation: Any) -> Any:
    origin = get_origin(annotation)
    if origin is UnionType:
        return Union

    return origin


def is_optional(annotation: Any) -> bool:
    origin = normalized_origin(annotation)
    if origin is list:
        return True

    if origin is Union and NoneType in get_args(annotation):
        return True

    return False


def _datetime_validator(x: str) -> bool:
    try:
        datetime.strptime(x, "%Y-%m-%d %H:%M:%S")
        return True
    except ValueError:
        return False


def _date_validator(x: str) -> bool:
    try:
        datetime.strptime(x, "%Y-%m-%d")
        return True
    except ValueError:
        return False


string_value_type_validators = {
    int: str.isdigit,
    float: lambda x: x.replace(".", "").isdigit(),
    bool: lambda x: x.lower() in {"true", "false", "yes", "no", "1", "0"},
    datetime: _datetime_validator,
    date: _date_validator,
}


def _is_valid_type(value: Any, allowed_types: list[type]) -> bool:
    for allowed_type in allowed_types:
        if allowed_type is type(None):
            continue

        if allowed_type not in string_value_type_validators:
            return True

        if string_value_type_validators[allowed_type](value):
            return True

    return False


class Form:
    __form_method__ = "POST"

    @classmethod
    def matches_form_data(cls, form_data: dict[str, Any]) -> bool:
        annotations = get_annotations(cls)

        allowed_keys = set(annotations.keys())
        required_keys = {
            key for key, value in annotations.items() if not is_optional(value)
        }

        form_data_keys = set(form_data.keys())
        has_missing_required_keys = required_keys - form_data_keys
        has_extra_keys = form_data_keys > allowed_keys
        if has_missing_required_keys or has_extra_keys:
            return False  # Form data keys do not match the expected keys

        for key, value in annotations.items():
            optional = key not in required_keys
            if key not in form_data and not optional:
                return False

            allowed_types = get_args(value)
            if not allowed_types:
                allowed_types = [value]

            if get_origin(value) is list and not all(
                _is_valid_type(item, allowed_types) for item in form_data[key]
            ):
                return False

            if key in form_data and not _is_valid_type(
                form_data[key][0], allowed_types
            ):
                return False

        return True  # All fields match


class Route:
    """Base class for creating HTTP route handlers in Serv applications.

    Route classes provide a structured way to handle HTTP requests by defining
    methods that correspond to HTTP methods (GET, POST, etc.) and form handlers.
    They support automatic request parsing, response type annotations, error
    handling, and dependency injection.

    The Route class automatically discovers handler methods based on their
    signatures and annotations:
    - Methods with Request subclass parameters become HTTP method handlers
    - Methods with Form subclass parameters become form handlers
    - Methods with Exception parameters become error handlers
    - Return type annotations determine response wrapper classes

    Examples:
        Basic route with HTTP method handlers:

        ```python
        from serv.routes import Route, GetRequest, PostRequest
        from serv.responses import JsonResponse, TextResponse
        from typing import Annotated

        class UserRoute(Route):
            async def handle_get(self, request: GetRequest) -> Annotated[dict, JsonResponse]:
                user_id = request.path_params.get("id")
                return {"id": user_id, "name": "John Doe"}

            async def handle_post(self, request: PostRequest) -> Annotated[str, TextResponse]:
                data = await request.json()
                # Create user logic here
                return "User created successfully"
        ```

        Route with form handling:

        ```python
        from serv.routes import Route, Form
        from serv.responses import HtmlResponse
        from typing import Annotated

        class ContactForm(Form):
            name: str
            email: str
            message: str

        class ContactRoute(Route):
            async def handle_get(self, request: GetRequest) -> Annotated[str, HtmlResponse]:
                return '''
                <form method="post">
                    <input name="name" placeholder="Name" required>
                    <input name="email" type="email" placeholder="Email" required>
                    <textarea name="message" placeholder="Message" required></textarea>
                    <button type="submit">Send</button>
                </form>
                '''

            async def handle_contact_form(self, form: ContactForm) -> Annotated[str, HtmlResponse]:
                # Process the form submission
                await self.send_email(form.email, form.name, form.message)
                return "<h1>Thank you! Your message has been sent.</h1>"
        ```

        Route with error handling:

        ```python
        from serv.routes import Route
        from serv.responses import JsonResponse
        from typing import Annotated

        class ValidationError(Exception):
            def __init__(self, message: str):
                self.message = message

        class ApiRoute(Route):
            async def handle_post(self, request: PostRequest) -> Annotated[dict, JsonResponse]:
                data = await request.json()
                if not data.get("email"):
                    raise ValidationError("Email is required")
                return {"status": "success"}

            async def handle_validation_error(self, error: ValidationError) -> Annotated[dict, JsonResponse]:
                return {"error": error.message, "status": "validation_failed"}
        ```

        Route with dependency injection:

        ```python
        from bevy import dependency
        from serv.app import App

        class DatabaseRoute(Route):
            async def handle_get(
                self,
                request: GetRequest,
                app: App = dependency()
            ) -> Annotated[dict, JsonResponse]:
                # Access app instance and its services
                plugin = app.get_plugin("database")
                data = await plugin.fetch_data()
                return {"data": data}
        ```

        Advanced route with multiple forms:

        ```python
        class LoginForm(Form):
            username: str
            password: str

        class RegisterForm(Form):
            __form_method__ = "POST"
            username: str
            email: str
            password: str
            confirm_password: str

        class AuthRoute(Route):
            async def handle_login_form(self, form: LoginForm) -> Annotated[str, HtmlResponse]:
                if self.authenticate(form.username, form.password):
                    return "<h1>Login successful!</h1>"
                else:
                    return "<h1>Invalid credentials</h1>"

            async def handle_register_form(self, form: RegisterForm) -> Annotated[str, HtmlResponse]:
                if form.password != form.confirm_password:
                    return "<h1>Passwords don't match</h1>"

                await self.create_user(form.username, form.email, form.password)
                return "<h1>Registration successful!</h1>"
        ```

    Note:
        Route classes are automatically instantiated by the router when a matching
        request is received. They can access plugin configuration and services
        through dependency injection, and their methods can return Response objects
        or use annotated return types for automatic response wrapping.
    """

    __method_handlers__: dict[str, str]
    __error_handlers__: dict[type[Exception], list[str]]
    __form_handlers__: dict[str, dict[type[Form], list[str]]]
    __annotated_response_wrappers__: dict[str, type[Response]]

    _plugin: "Plugin | None"

    def __init_subclass__(cls) -> None:
        cls.__method_handlers__ = {}
        cls.__error_handlers__ = defaultdict(list)
        cls.__form_handlers__ = defaultdict(lambda: defaultdict(list))
        cls.__annotated_response_wrappers__ = {}

        try:
            get_type_hints(cls, include_extras=True)
        except Exception:
            pass

        for name in dir(cls):
            if name.startswith("_"):
                continue

            member = getattr(cls, name)
            if not callable(member):
                continue

            sig = signature(member)
            params = list(sig.parameters.values())

            if not params:
                continue

            if len(params) > 1:
                second_arg_annotation = params[1].annotation
                if isinstance(second_arg_annotation, type) and issubclass(
                    second_arg_annotation, Request
                ):
                    method = MethodMapping.get(second_arg_annotation)
                    if method:
                        cls.__method_handlers__[method] = name
                        try:
                            handler_type_hints = get_type_hints(
                                member, include_extras=True
                            )
                            return_annotation = handler_type_hints.get("return")
                        except Exception:
                            return_annotation = None

                        if (
                            return_annotation
                            and get_origin(return_annotation) is Annotated
                        ):
                            args = get_args(return_annotation)
                            if (
                                len(args) == 2
                                and isinstance(args[1], type)
                                and issubclass(args[1], Response)
                            ):
                                cls.__annotated_response_wrappers__[name] = args[1]

                elif isinstance(second_arg_annotation, type) and issubclass(
                    second_arg_annotation, Form
                ):
                    form_type = second_arg_annotation
                    cls.__form_handlers__[form_type.__form_method__][form_type].append(
                        name
                    )

                elif isinstance(second_arg_annotation, type) and issubclass(
                    second_arg_annotation, Exception
                ):
                    cls.__error_handlers__[second_arg_annotation] = name

    async def __call__(
        self,
        request: Request = dependency(),
        container: Container = dependency(),
        response_builder: ResponseBuilder = dependency(),
    ):
        handler_result = await self._handle_request(request, container)

        if isinstance(handler_result, Response):
            response_builder.set_status(handler_result.status_code)
            for header, value in handler_result.headers.items():
                response_builder.add_header(header, value)
            response_builder.body(handler_result.render())
        else:
            raise TypeError(
                f"Route handler for {request.method} '{request.path}' returned a "
                f"{type(handler_result).__name__!r} but was expected to return a Response instance or use an "
                f"Annotated response type."
            )

    @property
    @inject
    def plugin(self, app: "serv.App" = dependency()) -> Plugin | None:
        if hasattr(self, "_plugin"):
            return self._plugin

        try:
            self._plugin = pl.find_plugin_spec(
                Path(sys.modules[self.__module__].__file__)
            )
        except Exception:
            type(self)._plugin = None

        return self._plugin

    async def _handle_request(self, request: Request, container: Container) -> Any:
        method = request.method
        handler = None
        handler_name = None
        args_to_pass = []

        if self.__form_handlers__.get(method):
            form_data = await request.form()
            for form_type, form_handler_names in self.__form_handlers__[method].items():
                if form_type.matches_form_data(form_data):
                    for name_in_list in form_handler_names:
                        try:
                            parsed_form = await request.form(form_type, data=form_data)
                            handler = getattr(self, name_in_list)
                            handler_name = name_in_list
                            args_to_pass = [parsed_form]
                            break
                        except Exception as e:
                            return await container.call(self._error_handler, e)
                    if handler:
                        break

        if not handler and method in self.__method_handlers__:
            handler_name = self.__method_handlers__[method]
            handler = getattr(self, handler_name)
            args_to_pass = [request]

        if not handler:
            return await container.call(
                self._error_handler,
                HTTPMethodNotAllowedException(
                    f"{type(self).__name__} does not support {method} or a matching form handler for provided data.",
                    list(
                        self.__method_handlers__.keys() | self.__form_handlers__.keys()
                    ),
                ),
            )

        try:
            handler_output_data = await container.call(handler, args_to_pass[0])
            if handler_name and handler_name in self.__annotated_response_wrappers__:
                wrapper_class = self.__annotated_response_wrappers__[handler_name]
                if isinstance(handler_output_data, tuple):
                    response = wrapper_class(*handler_output_data)
                else:
                    response = wrapper_class(handler_output_data)
            elif isinstance(handler_output_data, Response):
                response = handler_output_data
            else:
                raise TypeError(
                    f"Route handler for {request.method} '{request.path}' returned a "
                    f"{type(handler_output_data).__name__!r} but was expected to return a Response instance or use an "
                    f"Annotated response type."
                )

            response.set_created_by(self.plugin)
            return response

        except Exception as e:
            return await container.call(self._error_handler, e)

    async def _error_handler(
        self, exception: Exception, container: Container = dependency()
    ) -> Response:
        for error_type, handler_name in self.__error_handlers__.items():
            if isinstance(exception, error_type):
                try:
                    handler = getattr(self, handler_name)
                    return await container.call(handler, exception)
                except Exception as e:
                    e.__cause__ = exception
                    return await container.call(self._error_handler, e)

        raise exception
