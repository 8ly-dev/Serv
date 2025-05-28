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
import serv.extensions.loader as pl
from serv.exceptions import HTTPMethodNotAllowedException
from serv.extensions import Listener
from serv.requests import Request
from serv.responses import ResponseBuilder
from serv.injectors import Header, Cookie, Query


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

            # Handle method naming pattern (handle_<method>)
            if name.startswith('handle_'):
                method_part = name[7:]  # Remove 'handle_' prefix
                
                # Check if it's a standard HTTP method
                http_method = method_part.upper()
                if http_method in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD']:
                    cls.__method_handlers__[http_method].append({
                        'name': name,
                        'method': member,
                        'signature': sig
                    })
                    
                    # Store response wrapper if annotated
                    try:
                        handler_type_hints = get_type_hints(member, include_extras=True)
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
                    continue

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
            raise TypeError(
                f"Route handler for {request.method} '{request.path}' returned a "
                f"{type(handler_result).__name__!r} but was expected to return a Response instance or use an "
                f"Annotated response type."
            )

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

    def _analyze_handler_signature(self, handler_sig, request: Request) -> dict:
        """Analyze a handler's signature and determine what parameters it needs."""
        params = list(handler_sig.parameters.values())[1:]  # Skip 'self'
        analysis = {
            'required_params': [],
            'optional_params': [],
            'injectable_params': [],
            'score': 0
        }
        
        try:
            type_hints = get_type_hints(handler_sig, include_extras=True)
        except Exception:
            type_hints = {}
        
        for param in params:
            param_info = {
                'name': param.name,
                'annotation': param.annotation,
                'default': param.default,
                'has_default': param.default != param.empty
            }
            
            # Check if parameter is annotated with injection markers
            annotation = type_hints.get(param.name, param.annotation)
            if get_origin(annotation) is Annotated:
                args = get_args(annotation)
                if len(args) >= 2:
                    marker = args[1]
                    if isinstance(marker, (Header, Cookie, Query)):
                        param_info['injection_marker'] = marker
                        analysis['injectable_params'].append(param_info)
                        
                        # Check if the required data is available in the request
                        if isinstance(marker, Header) and marker.name in request.headers:
                            analysis['score'] += 10
                        elif isinstance(marker, Cookie) and marker.name in request.cookies:
                            analysis['score'] += 10
                        elif isinstance(marker, Query) and marker.name in request.query_params:
                            analysis['score'] += 10
                        elif marker.default is not None:
                            analysis['score'] += 5  # Has default value
                        elif param_info['has_default']:
                            analysis['score'] += 5  # Parameter has default
                        else:
                            analysis['score'] -= 5  # Required but not available
                        continue
            
            # Regular parameter handling
            if param_info['has_default']:
                analysis['optional_params'].append(param_info)
                analysis['score'] += 1
            else:
                analysis['required_params'].append(param_info)
                analysis['score'] -= 2  # Penalize required non-injectable params
        
        return analysis

    def _score_handler_compatibility(self, handler_info: dict, request: Request) -> int:
        """Score how well a handler matches the current request."""
        analysis = self._analyze_handler_signature(handler_info['signature'], request)
        base_score = analysis['score']
        
        # Bonus for having injectable parameters that match request data
        injectable_matches = len([
            p for p in analysis['injectable_params'] 
            if self._can_inject_parameter(p, request)
        ])
        
        # Penalty for having required non-injectable parameters
        required_non_injectable = len(analysis['required_params'])
        
        final_score = base_score + (injectable_matches * 5) - (required_non_injectable * 10)
        
        return final_score

    def _can_inject_parameter(self, param_info: dict, request: Request) -> bool:
        """Check if a parameter can be injected from the request."""
        if 'injection_marker' not in param_info:
            return False
            
        marker = param_info['injection_marker']
        
        if isinstance(marker, Header):
            return marker.name in request.headers or marker.default is not None
        elif isinstance(marker, Cookie):
            return marker.name in request.cookies or marker.default is not None
        elif isinstance(marker, Query):
            return marker.name in request.query_params or marker.default is not None
            
        return False

    async def _extract_handler_parameters(self, handler_info: dict, request: Request, container: Container) -> list:
        """Extract and prepare parameters for handler invocation."""
        analysis = self._analyze_handler_signature(handler_info['signature'], request)
        args = []
        
        # Handle injectable parameters
        for param_info in analysis['injectable_params']:
            marker = param_info['injection_marker']
            value = None
            
            if isinstance(marker, Header):
                value = request.headers.get(marker.name, marker.default)
            elif isinstance(marker, Cookie):
                value = request.cookies.get(marker.name, marker.default)
            elif isinstance(marker, Query):
                value = request.query_params.get(marker.name, marker.default)
            
            if value is None and not param_info['has_default']:
                raise ValueError(f"Required parameter '{param_info['name']}' not found in request")
                
            args.append(value)
        
        # Handle other parameters (try to inject from container or use defaults)
        for param_info in analysis['required_params'] + analysis['optional_params']:
            if param_info['has_default']:
                continue  # Will be handled by function call
                
            # Try to get from container based on type annotation
            try:
                if param_info['annotation'] != param_info.empty:
                    value = container.get(param_info['annotation'])
                    args.append(value)
            except Exception:
                if not param_info['has_default']:
                    raise ValueError(f"Cannot inject parameter '{param_info['name']}'")
        
        return args

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
                handler = handler_info['method']
                handler_name = handler_info['name']
                try:
                    args_to_pass = await self._extract_handler_parameters(handler_info, request, container)
                except Exception as e:
                    return await container.call(self._error_handler, e)
            else:
                # Multiple handlers, find the best match
                scored_handlers = []
                for handler_info in handlers:
                    score = self._score_handler_compatibility(handler_info, request)
                    scored_handlers.append((score, handler_info))
                
                # Sort by score (highest first)
                scored_handlers.sort(key=lambda x: x[0], reverse=True)
                
                # Try handlers in order of compatibility score
                for score, handler_info in scored_handlers:
                    try:
                        args_to_pass = await self._extract_handler_parameters(handler_info, request, container)
                        handler = handler_info['method']
                        handler_name = handler_info['name']
                        break
                    except Exception:
                        continue  # Try next handler
                
                if not handler:
                    return await container.call(
                        self._error_handler,
                        HTTPMethodNotAllowedException(
                            f"No compatible handler found for {method} request with provided parameters.",
                            list(self.__method_handlers__.keys() | self.__form_handlers__.keys())
                        ),
                    )

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
            if args_to_pass:
                handler_output_data = await container.call(handler, *args_to_pass)
            else:
                handler_output_data = await container.call(handler)
                
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
