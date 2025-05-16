from collections import defaultdict
from datetime import datetime, date
from inspect import get_annotations, signature
import json
from pathlib import Path
from types import NoneType, UnionType
from typing import Any, AsyncGenerator, Type, Union, get_args, get_origin, Annotated, get_type_hints

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

        allowed_keys = set(annotations.keys())
        required_keys = {key for key, value in annotations.items() if not is_optional(value)}

        form_data_keys = set(form_data.keys())
        has_missing_required_keys = required_keys - form_data_keys
        has_extra_keys = form_data_keys > allowed_keys
        if has_missing_required_keys or has_extra_keys:
            return False # Form data keys do not match the expected keys

        for key, value in annotations.items():
            optional = key not in required_keys
            if key not in form_data and not optional:
                return False
            
            allowed_types = get_args(value)
            if not allowed_types:
                allowed_types = [value]

            if (
                get_origin(value) is list and
                not all(_is_valid_type(item, allowed_types) for item in form_data[key])
            ):
                return False

            if key in form_data and not _is_valid_type(form_data[key][0], allowed_types):
                return False

        return True # All fields match 


class Route:
    __method_handlers__: dict[str, str]
    __error_handlers__: dict[Type[Exception], str]
    __form_handlers__: dict[str, dict[Type[Form], list[str]]]
    __annotated_response_wrappers__: dict[str, Type[Response]]

    def __init_subclass__(cls) -> None:
        cls.__method_handlers__ = {}
        cls.__error_handlers__ = defaultdict(list)
        cls.__form_handlers__ = defaultdict(lambda: defaultdict(list))
        cls.__annotated_response_wrappers__ = {}
        
        try:
            all_type_hints = get_type_hints(cls, include_extras=True)
        except Exception:
            all_type_hints = {}

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
                if isinstance(second_arg_annotation, type) and issubclass(second_arg_annotation, Request):
                    method = MethodMapping.get(second_arg_annotation)
                    if method:
                        cls.__method_handlers__[method] = name
                        try:
                            handler_type_hints = get_type_hints(member, include_extras=True)
                            return_annotation = handler_type_hints.get('return')
                        except Exception:
                            return_annotation = None
                            
                        if return_annotation and get_origin(return_annotation) is Annotated:
                            args = get_args(return_annotation)
                            if len(args) == 2 and isinstance(args[1], type) and issubclass(args[1], Response):
                                cls.__annotated_response_wrappers__[name] = args[1]

                elif isinstance(second_arg_annotation, type) and issubclass(second_arg_annotation, Form):
                    form_type = second_arg_annotation
                    cls.__form_handlers__[form_type.__form_method__][form_type].append(name)

                elif isinstance(second_arg_annotation, type) and issubclass(second_arg_annotation, Exception):
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
        

    async def _handle_request(self, request: Request, container: Container) -> Any:
        method = request.method
        handler = None
        handler_name = None
        is_form_handler = False
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
                            is_form_handler = True
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
                    list(self.__method_handlers__.keys() | self.__form_handlers__.keys())
                )
            )

        try:
            if is_form_handler:
                handler_output_data = await container.call(handler, args_to_pass[0])
            else:
                handler_output_data = await container.call(handler, args_to_pass[0])

            if handler_name and handler_name in self.__annotated_response_wrappers__:
                wrapper_class = self.__annotated_response_wrappers__[handler_name]
                return wrapper_class(handler_output_data)
            
            return handler_output_data
        
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
