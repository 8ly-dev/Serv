from collections import defaultdict
from datetime import datetime, date
from inspect import get_annotations, signature
import json
from pathlib import Path
from types import NoneType, UnionType
from typing import Any, AsyncGenerator, Type, Union, get_args, get_origin

from bevy import dependency
from bevy.containers import Container

from serv.exceptions import HTTPMethodNotAllowedException
from serv.requests import Request
from serv.responses import ResponseBuilder


class Response:
    def __init__(self, status_code: int, body: str | bytes | None = None, headers: dict[str, str] | None = None):
        self.status_code = status_code
        self.body = body or bytes()
        self.headers = headers or {}

    async def render(self) -> AsyncGenerator[bytes, None]:
        yield self.body


class RedirectResponse(Response):
    def __init__(self, url: str, status_code: int = 302):
        super().__init__(status_code)
        self.headers["Location"] = url


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
    def __init__(self, file: bytes, filename: str, status_code: int = 200, content_type: str = "application/octet-stream"):
        super().__init__(status_code)
        self.body = file
        self.headers["Content-Type"] = content_type
        self.headers["Content-Disposition"] = f"attachment; filename={filename}"


class Jinja2Response(Response):
    def __init__(self, template: str, context: dict[str, Any], status_code: int = 200):
        super().__init__(status_code)
        self.template = template
        self.context = context
        self.headers["Content-Type"] = "text/html"

    def render(self) -> AsyncGenerator[bytes, None]:
        from jinja2 import Environment, FileSystemLoader

        env = Environment(loader=FileSystemLoader(Path.cwd() / "templates"), enable_async=True)
        template = env.get_template(self.template)
        return template.generate_async(**self.context)


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
        print("--------------------------------")
        print("PROCESSING FORM", cls.__name__)
        print()
        print()
        print()

        allowed_keys = set(annotations.keys())
        required_keys = {key for key, value in annotations.items() if not is_optional(value)}

        form_data_keys = set(form_data.keys())
        has_missing_required_keys = required_keys - form_data_keys
        has_extra_keys = form_data_keys > allowed_keys
        if has_missing_required_keys or has_extra_keys:
            return False # Form data keys do not match the expected keys

        for key, value in annotations.items():
            print("- Checking Key", key, "Value", value)
            optional = key not in required_keys
            if key not in form_data and not optional:
                print("Key not in form data and not optional", key, form_data.keys())
                return False
            
            allowed_types = get_args(value)
            if not allowed_types:
                allowed_types = [value]

            if (
                get_origin(value) is list and
                not all(_is_valid_type(item, allowed_types) for item in form_data[key])
            ):
                print("Invalid list type", value)
                return False

            if key in form_data and not _is_valid_type(form_data[key][0], allowed_types):
                print("Invalid type", form_data[key][0], allowed_types)
                return False
            
            print("Key", key, "Value", form_data.get(key, "NOT SENT"), "Allowed types", allowed_types)

        print("All fields match")
        return True # All fields match 


class Route:
    __method_handlers__: dict[str, str]
    __error_handlers__: dict[Type[Exception], str]
    __form_handlers__: dict[str, dict[Type[Form], list[str]]]

    def __init_subclass__(cls) -> None:
        cls.__method_handlers__ = {}
        cls.__error_handlers__ = defaultdict(list)
        cls.__form_handlers__ = defaultdict(lambda: defaultdict(list))
        
        for name in dir(cls):
            if name.startswith("_"):
                continue

            handler = getattr(cls, name)
            if not callable(handler):
                continue

            sig = signature(handler)
            second_arg = list(sig.parameters.values())[1].annotation
            match second_arg:
                case type() as request if issubclass(request, Request):
                    method = MethodMapping.get(request)
                    cls.__method_handlers__[method] = name
                case type() as form_type if issubclass(form_type, Form):
                    cls.__form_handlers__[form_type.__form_method__][form_type].append(name)
                case type() as exception if issubclass(exception, Exception):
                    cls.__error_handlers__[exception] = name

    async def __call__(
        self, 
        request: Request = dependency(), 
        container: Container = dependency(),
        response_builder: ResponseBuilder = dependency(),
    ):
        response = await self._handle_request(request, container)
        response_builder.set_status(response.status_code)
        for header, value in response.headers.items():
            response_builder.add_header(header, value)

        response_builder.body(response.render())
        

    async def _handle_request(self, request: Request, container: Container) -> Response:
        method = request.method
        if self.__form_handlers__.get(method):
            form_data = await request.form()
            for form_type, form_handlers in self.__form_handlers__[method].items():
                # TODO: This is a hack to get the form data for the form type
                # TODO: We should probably just pass the possible form types to request.form
                # TODO: and let it decide which one to use
                if form_type.matches_form_data(form_data):
                    for handler_name in form_handlers:
                        try:
                            handler = getattr(self, handler_name)
                            form = await request.form(form_type, data=form_data)
                            return await container.call(handler, form)
                        except Exception as e:
                            return await container.call(self._error_handler, e)

        if method not in self.__method_handlers__:
            return await container.call(
                self._error_handler,
                HTTPMethodNotAllowedException(
                    f"{type(self).__name__} does not support {method}", 
                    list(self.__method_handlers__.keys() | self.__form_handlers__.keys())
                )
            )

        handler_name = self.__method_handlers__[method]
        try:
            handler = getattr(self, handler_name)
            return await container.call(handler, request)
        except Exception as e:
            return await container.call(self._error_handler, e)
    
    async def _error_handler(self, exception: Exception, container: Container = dependency()) -> Response:
        for error_type, handler_name in self.__error_handlers__.items():
            if isinstance(exception, error_type):
                try:
                    handler = getattr(self, handler_name)
                    return await container.call(handler, exception)
                except Exception as e:
                    e.__cause__ = exception
                    return await container.call(self._error_handler, e)
                
        raise exception
