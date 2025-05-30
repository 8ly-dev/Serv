import json
import sys
from collections import defaultdict
from collections.abc import AsyncGenerator
from datetime import date, datetime
from functools import wraps
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
import serv.app as app
import serv.extensions.loader as pl
from serv.exceptions import HTTPMethodNotAllowedException
from serv.extensions import Listener
from serv.injectors import Cookie, Header, Query
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
    def _get_template_locations(extension: "pl.ExtensionSpec"):
        if not extension:
            raise RuntimeError("Jinja2Response cannot be used outside of a extension.")

        return [
            Path.cwd() / "templates" / extension.name,
            extension.path / "templates",
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


class _HandleDecorator:
    """Decorator class for marking route handler methods with HTTP methods."""

    def __init__(self, methods: set[str]):
        self.methods = methods

    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        # Store the HTTP methods this handler supports
        wrapper.__handle_methods__ = self.methods
        return wrapper

    def __or__(self, other):
        """Support for @handle.GET | handle.POST syntax"""
        if isinstance(other, _HandleDecorator):
            return _HandleDecorator(self.methods | other.methods)
        return NotImplemented


class _HandleRegistry:
    """Registry that provides method decorators like @handle.GET, @handle.POST"""

    def __init__(self):
        # Create decorator instances for each HTTP method
        self.GET = _HandleDecorator({"GET"})
        self.POST = _HandleDecorator({"POST"})
        self.PUT = _HandleDecorator({"PUT"})
        self.DELETE = _HandleDecorator({"DELETE"})
        self.PATCH = _HandleDecorator({"PATCH"})
        self.OPTIONS = _HandleDecorator({"OPTIONS"})
        self.HEAD = _HandleDecorator({"HEAD"})
        self.FORM = _HandleDecorator({"FORM"})  # Special form handler


# Create the global handle instance
handle = _HandleRegistry()


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
    naming patterns and signatures:
    - Methods named `handle_<method>` become HTTP method handlers (e.g., `handle_get`, `handle_post`)
    - Methods with Form subclass parameters become form handlers
    - Methods with Exception parameters become error handlers
    - Return type annotations determine response wrapper classes
    - Handler selection is based on signature matching with request data

    Examples:
        Basic route with HTTP method handlers:

        ```python
        from serv.routes import Route
        from serv.responses import JsonResponse, TextResponse
        from serv.injectors import Query, Header
        from typing import Annotated

        class UserRoute(Route):
            async def handle_get(self, user_id: Annotated[str, Query("id")]) -> Annotated[dict, JsonResponse]:
                return {"id": user_id, "name": "John Doe"}

            async def handle_post(self, data: dict) -> Annotated[str, TextResponse]:
                # Create user logic here
                return "User created successfully"
        ```

        Route with multiple GET handlers based on parameters:

        ```python
        class ProductRoute(Route):
            # Handler for requests with 'id' query parameter
            async def handle_get(self, product_id: Annotated[str, Query("id")]) -> Annotated[dict, JsonResponse]:
                return {"id": product_id, "name": "Product Name"}

            # Handler for requests with 'category' query parameter
            async def handle_get_by_category(self, category: Annotated[str, Query("category")]) -> Annotated[list, JsonResponse]:
                return [{"id": 1, "name": "Product 1"}, {"id": 2, "name": "Product 2"}]

            # Handler for requests with no specific parameters (fallback)
            async def handle_get_all(self) -> Annotated[list, JsonResponse]:
                return [{"id": 1, "name": "All Products"}]
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
            async def handle_get(self) -> Annotated[str, HtmlResponse]:
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

        Route with header and cookie injection:

        ```python
        from serv.injectors import Header, Cookie

        class AuthRoute(Route):
            async def handle_get(
                self,
                auth_token: Annotated[str, Header("Authorization")],
                session_id: Annotated[str, Cookie("session_id")]
            ) -> Annotated[dict, JsonResponse]:
                # Validate token and session
                return {"authenticated": True, "user": "john_doe"}
        ```

    Note:
        Route classes are automatically instantiated by the router when a matching
        request is received. Handler methods are selected based on the best match
        between the request data and the method's parameter signature. Methods with
        more specific parameter requirements will be preferred over generic handlers.
    """

    __method_handlers__: dict[str, list[dict]]
    __error_handlers__: dict[type[Exception], list[str]]
    __form_handlers__: dict[str, dict[type[Form], list[str]]]
    __annotated_response_wrappers__: dict[str, type[Response]]

    _extension: "Listener | None"

    def __init_subclass__(cls) -> None:
        cls.__method_handlers__ = defaultdict(list)
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

            # Store response wrapper if annotated (applies to ALL handlers)
            try:
                handler_type_hints = get_type_hints(member, include_extras=True)
                return_annotation = handler_type_hints.get("return")
            except Exception:
                return_annotation = None

            if return_annotation and get_origin(return_annotation) is Annotated:
                args = get_args(return_annotation)
                if (
                    len(args) == 2
                    and isinstance(args[1], type)
                    and issubclass(args[1], Response)
                ):
                    cls.__annotated_response_wrappers__[name] = args[1]

            # Handle decorator-based method detection
            if hasattr(member, "__handle_methods__"):
                for http_method in member.__handle_methods__:
                    if http_method == "FORM":
                        # Special handling for FORM - these will be detected by form parameter analysis
                        continue
                    cls.__method_handlers__[http_method].append(
                        {"name": name, "method": member, "signature": sig}
                    )

            # Handle form handlers and error handlers (existing logic)
            if len(params) > 1:
                second_arg_annotation = params[1].annotation

                if isinstance(second_arg_annotation, type) and issubclass(
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
            # This should never happen if _handle_request is working correctly,
            # but provide a detailed error message just in case
            import inspect

            # Try to determine which handler was called
            handler_info = "unknown"
            try:
                # Get the current frame and look for handler information
                frame = inspect.currentframe()
                if frame and frame.f_back:
                    local_vars = frame.f_back.f_locals
                    if "handler_name" in local_vars:
                        handler_info = (
                            f"{type(self).__name__}.{local_vars['handler_name']}()"
                        )
            except Exception:
                pass

            error_msg = (
                f"Route __call__ received non-Response object:\n"
                f"  Handler: {handler_info}\n"
                f"  Route: {request.method} '{request.path}'\n"
                f"  Received: {type(handler_result).__name__!r} ({repr(handler_result)[:100]}{'...' if len(repr(handler_result)) > 100 else ''})\n"
                f"  Expected: Response instance\n"
                f"  Note: This suggests an issue in _handle_request method - annotated response wrappers should have been applied"
            )

            raise TypeError(error_msg)

    @property
    @inject
    def extension(self, app: "serv.App" = dependency()) -> Listener | None:
        if hasattr(self, "_extension"):
            return self._extension

        try:
            self._extension = pl.find_extension_spec(
                Path(sys.modules[self.__module__].__file__)
            )
        except Exception:
            type(self)._extension = None

        return self._extension

    @inject
    async def emit(
        self, event: str, emitter: "app.EventEmitter" = dependency(), /, **kwargs: Any
    ):
        return await emitter.emit(event, **kwargs)

    def _analyze_handler_signature(self, handler_sig, request: Request) -> dict:
        """Analyze a handler's signature and determine what parameters it needs."""
        params = list(handler_sig.parameters.values())[1:]  # Skip 'self'
        analysis = {
            "required_params": [],
            "optional_params": [],
            "injectable_params": [],
            "score": 0,
        }

        try:
            type_hints = get_type_hints(handler_sig, include_extras=True)
        except Exception:
            type_hints = {}

        for param in params:
            param_info = {
                "name": param.name,
                "annotation": param.annotation,
                "default": param.default,
                "has_default": param.default != param.empty,
            }

            # Check if parameter is annotated with injection markers
            annotation = type_hints.get(param.name, param.annotation)
            if get_origin(annotation) is Annotated:
                args = get_args(annotation)
                if len(args) >= 2:
                    marker = args[1]
                    if isinstance(marker, Header | Cookie | Query):
                        param_info["injection_marker"] = marker
                        analysis["injectable_params"].append(param_info)

                        # Check if the required data is available in the request
                        if (
                            isinstance(marker, Header)
                            and marker.name in request.headers
                        ):
                            analysis["score"] += 10
                        elif (
                            isinstance(marker, Cookie)
                            and marker.name in request.cookies
                        ):
                            analysis["score"] += 10
                        elif (
                            isinstance(marker, Query)
                            and marker.name in request.query_params
                        ):
                            analysis["score"] += 10
                        elif marker.default is not None:
                            analysis["score"] += 5  # Has default value
                        elif param_info["has_default"]:
                            analysis["score"] += 5  # Parameter has default
                        else:
                            analysis["score"] -= 5  # Required but not available
                        continue

            # Regular parameter handling
            if param_info["has_default"]:
                analysis["optional_params"].append(param_info)
                analysis["score"] += 1
            else:
                analysis["required_params"].append(param_info)
                analysis["score"] -= 2  # Penalize required non-injectable params

        return analysis

    def _calculate_handler_specificity(
        self, handler_info: dict, request: Request, kwargs: dict
    ) -> int:
        """Calculate how specific/targeted this handler is for the current request."""
        sig = handler_info["signature"]
        params = list(sig.parameters.values())[1:]  # Skip 'self'

        try:
            type_hints = get_type_hints(sig, include_extras=True)
        except Exception:
            type_hints = {}

        score = 0
        injectable_params_with_data = 0

        for param in params:
            param_name = param.name
            param_annotation = type_hints.get(param_name, param.annotation)

            # Check if this parameter was actually satisfied from the request data
            if param_name in kwargs:
                if get_origin(param_annotation) is Annotated:
                    args = get_args(param_annotation)
                    if len(args) >= 2:
                        marker = args[1]

                        # Higher score for parameters that got actual data from request
                        if isinstance(marker, Header) and (
                            marker.name in request.headers
                            or marker.name.lower() in request.headers
                        ):
                            injectable_params_with_data += 1
                            score += 10  # High score for actual header match
                        elif (
                            isinstance(marker, Cookie)
                            and marker.name in request.cookies
                        ):
                            injectable_params_with_data += 1
                            score += 10  # High score for actual cookie match
                        elif (
                            isinstance(marker, Query)
                            and marker.name in request.query_params
                        ):
                            injectable_params_with_data += 1
                            score += 10  # High score for actual query param match
                        elif hasattr(marker, "default") and marker.default is not None:
                            score += 1  # Low score for default values

                elif param.default != param.empty:
                    score += 1  # Low score for parameter defaults
                else:
                    score += 5  # Medium score for container-injected parameters

        # Prefer handlers with more injectable parameters that have actual data
        score += injectable_params_with_data * 5

        return score

    def _can_inject_parameter(self, param_info: dict, request: Request) -> bool:
        """Check if a parameter can be injected from the request."""
        if "injection_marker" not in param_info:
            return False

        marker = param_info["injection_marker"]

        if isinstance(marker, Header):
            return marker.name in request.headers or marker.default is not None
        elif isinstance(marker, Cookie):
            return marker.name in request.cookies or marker.default is not None
        elif isinstance(marker, Query):
            return marker.name in request.query_params or marker.default is not None

        return False

    async def _extract_handler_parameters(
        self, handler_info: dict, request: Request, container: Container
    ) -> dict:
        """Extract and prepare parameters for handler invocation."""
        sig = handler_info["signature"]
        params = list(sig.parameters.values())[1:]  # Skip 'self'
        kwargs = {}

        try:
            type_hints = get_type_hints(sig, include_extras=True)
        except Exception:
            type_hints = {}

        for param in params:
            param_name = param.name
            param_annotation = type_hints.get(param_name, param.annotation)
            value = None

            # Check for injection annotations
            if get_origin(param_annotation) is Annotated:
                args = get_args(param_annotation)
                if len(args) >= 2:
                    marker = args[1]

                    if isinstance(marker, Header):
                        # HTTP headers are case-insensitive, so try lowercase
                        header_value = request.headers.get(
                            marker.name
                        ) or request.headers.get(marker.name.lower())
                        value = (
                            header_value if header_value is not None else marker.default
                        )
                    elif isinstance(marker, Cookie):
                        value = request.cookies.get(marker.name, marker.default)
                    elif isinstance(marker, Query):
                        value = request.query_params.get(marker.name, marker.default)

            # If no injection marker found and no value extracted, try container injection
            if value is None:
                try:
                    # Extract the actual type if it's an Annotated type
                    injection_type = param_annotation
                    if get_origin(param_annotation) is Annotated:
                        injection_type = get_args(param_annotation)[0]

                    if injection_type != param.empty and injection_type is not type(
                        None
                    ):
                        value = container.get(injection_type)
                except Exception:
                    pass

            # If still no value and parameter has a default, we'll let the function handle it
            if value is None and param.default != param.empty:
                continue  # Skip this parameter, let default value be used

            # If still no value and it's required, raise an error
            if value is None:
                # Get detailed information about the handler for better error reporting
                handler_class = type(self).__name__
                handler_module = type(self).__module__
                handler_method_name = handler_info.get("name", "unknown")

                # Try to get the file and line number of the handler method
                import inspect

                handler_file = "unknown"
                handler_line = "unknown"
                try:
                    handler_method = handler_info.get("method")
                    if handler_method:
                        handler_source = inspect.getsourcefile(handler_method)
                        handler_lines = inspect.getsourcelines(handler_method)
                        if handler_source:
                            handler_file = handler_source
                        if handler_lines:
                            handler_line = handler_lines[1]
                except Exception:
                    pass

                error_msg = (
                    f"Required parameter could not be resolved:\n"
                    f"  Parameter: '{param_name}' (type: {param_annotation})\n"
                    f"  Handler: {handler_class}.{handler_method_name}()\n"
                    f"  Module: {handler_module}\n"
                    f"  File: {handler_file}\n"
                    f"  Line: {handler_line}\n"
                    f"  Suggestion: Add dependency injection annotation or provide a default value"
                )

                raise ValueError(error_msg)

            kwargs[param_name] = value

        return kwargs

    async def _handle_request(self, request: Request, container: Container) -> Any:
        method = request.method
        handler = None
        handler_name = None
        args_to_pass = []

        # Handle form submissions first
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

        # Handle method handlers with signature matching
        if not handler and method in self.__method_handlers__:
            handlers = self.__method_handlers__[method]

            if len(handlers) == 1:
                # Only one handler, use it
                handler_info = handlers[0]
                handler = handler_info["method"]
                handler_name = handler_info["name"]
                try:
                    kwargs_to_pass = await self._extract_handler_parameters(
                        handler_info, request, container
                    )
                except Exception as e:
                    return await container.call(self._error_handler, e)
            else:
                # Multiple handlers, find the best match
                compatible_handlers = []

                for handler_info in handlers:
                    try:
                        kwargs_to_pass_temp = await self._extract_handler_parameters(
                            handler_info, request, container
                        )
                        # Count how many injectable parameters actually got values from the request
                        score = self._calculate_handler_specificity(
                            handler_info, request, kwargs_to_pass_temp
                        )
                        compatible_handlers.append(
                            (score, handler_info, kwargs_to_pass_temp)
                        )
                    except Exception:
                        continue  # Handler is not compatible

                if not compatible_handlers:
                    return await container.call(
                        self._error_handler,
                        HTTPMethodNotAllowedException(
                            f"No compatible handler found for {method} request with provided parameters.",
                            list(
                                self.__method_handlers__.keys()
                                | self.__form_handlers__.keys()
                            ),
                        ),
                    )

                # Sort by score (highest first) and take the best match
                compatible_handlers.sort(key=lambda x: x[0], reverse=True)
                score, handler_info, kwargs_to_pass = compatible_handlers[0]
                handler = handler_info["method"]
                handler_name = handler_info["name"]

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
            # Call handler with extracted parameters
            if "kwargs_to_pass" in locals() and kwargs_to_pass:
                handler_output_data = await container.call(
                    handler, self, **kwargs_to_pass
                )
            elif "args_to_pass" in locals() and args_to_pass:
                # For form handlers, call directly to avoid container injection conflicts
                handler_output_data = await handler(*args_to_pass)
            else:
                handler_output_data = await container.call(handler, self)

            if handler_name and handler_name in self.__annotated_response_wrappers__:
                wrapper_class = self.__annotated_response_wrappers__[handler_name]
                if isinstance(handler_output_data, tuple):
                    response = wrapper_class(*handler_output_data)
                else:
                    response = wrapper_class(handler_output_data)
            elif isinstance(handler_output_data, Response):
                response = handler_output_data
            else:
                # Check if this handler should have had an annotated response wrapper
                should_have_wrapper = False
                wrapper_info = ""

                if handler_name:
                    # Check if the handler method has an annotated return type
                    try:
                        if hasattr(self, handler_name):
                            handler_method = getattr(self, handler_name)
                            from typing import get_args, get_origin, get_type_hints

                            type_hints = get_type_hints(
                                handler_method, include_extras=True
                            )
                            return_annotation = type_hints.get("return")

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
                                    should_have_wrapper = True
                                    wrapper_info = (
                                        f" (should be wrapped in {args[1].__name__})"
                                    )
                    except Exception:
                        pass

                # Get detailed information about the handler for better error reporting
                handler_class = type(self).__name__
                handler_module = type(self).__module__

                # Try to get the file and line number of the handler method
                import inspect

                handler_file = "unknown"
                handler_line = "unknown"
                try:
                    handler_source = inspect.getsourcefile(handler)
                    handler_lines = inspect.getsourcelines(handler)
                    if handler_source:
                        handler_file = handler_source
                    if handler_lines:
                        handler_line = handler_lines[
                            1
                        ]  # Line number where the function starts
                except Exception:
                    pass

                # Create a detailed error message
                if should_have_wrapper:
                    error_msg = (
                        f"Route handler has annotated response type but wrapper was not applied:\n"
                        f"  Handler: {handler_class}.{handler_name}()\n"
                        f"  Module: {handler_module}\n"
                        f"  File: {handler_file}\n"
                        f"  Line: {handler_line}\n"
                        f"  Route: {request.method} '{request.path}'\n"
                        f"  Returned: {type(handler_output_data).__name__!r} ({repr(handler_output_data)[:100]}{'...' if len(repr(handler_output_data)) > 100 else ''})\n"
                        f"  Expected wrapper: {wrapper_info}\n"
                        f"  Issue: Annotated response wrapper was not applied (this is a framework bug)\n"
                        f"  Debug info: handler_name='{handler_name}', in_wrappers={handler_name in self.__annotated_response_wrappers__ if handler_name else False}"
                    )
                else:
                    error_msg = (
                        f"Route handler returned wrong type:\n"
                        f"  Handler: {handler_class}.{handler_name}()\n"
                        f"  Module: {handler_module}\n"
                        f"  File: {handler_file}\n"
                        f"  Line: {handler_line}\n"
                        f"  Route: {request.method} '{request.path}'\n"
                        f"  Returned: {type(handler_output_data).__name__!r} ({repr(handler_output_data)[:100]}{'...' if len(repr(handler_output_data)) > 100 else ''})\n"
                        f"  Expected: Response instance or use an Annotated response type"
                    )

                raise TypeError(error_msg)

            response.set_created_by(self.extension)
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
