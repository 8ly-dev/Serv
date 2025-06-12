"""Handler processing utilities for route management."""

import inspect
from dataclasses import dataclass
from typing import Any

from bevy.containers import Container

from ..exceptions import HTTPBadRequestException, HTTPMethodNotAllowedException
from ..http.requests import Request
from ..http.response_utils import BaseResponse as Response
from ..utils.type_utils import AnnotationEvaluationError, get_safe_type_hints
from .parameter_utils import ParameterAnalyzer, ParameterExtractor


@dataclass
class FormHandlerResult:
    """Result from attempting to handle a form submission."""

    handler: Any
    handler_info: dict
    args: list


@dataclass
class MethodHandlerResult:
    """Result from attempting to handle an HTTP method."""

    handler: Any
    handler_info: dict
    kwargs: dict


@dataclass
class HandlerError:
    """Error result from handler processing."""

    response: Any


class NoHandlerFound:
    """Marker for when no handler is found."""

    pass


class HandlerProcessor:
    """Processes and manages route handlers."""

    def __init__(self, route_instance):
        self.route = route_instance
        self.analyzer = ParameterAnalyzer()
        self.extractor = ParameterExtractor()

    def analyze_handler_signature(self, handler_sig, request: Request) -> dict:
        """Analyze a handler's signature and determine what parameters it needs."""
        params = list(handler_sig.parameters.values())[1:]  # Skip 'self'
        analysis = {
            "required_params": [],
            "optional_params": [],
            "injectable_params": [],
            "score": 0,
        }

        type_hints = get_safe_type_hints(handler_sig, include_extras=True)

        for param in params:
            param_analysis = self.analyzer.analyze_parameter(param, type_hints)

            if param_analysis.injection_marker:
                analysis["injectable_params"].append(param_analysis)
                score = self.analyzer.score_injectable_parameter(
                    param_analysis.injection_marker, param_analysis, request
                )
                analysis["score"] += score
            else:
                target_list = (
                    "optional_params"
                    if param_analysis.has_default
                    else "required_params"
                )
                analysis[target_list].append(param_analysis)
                score = self.analyzer.score_regular_parameter(param_analysis)
                analysis["score"] += score

        return analysis

    def calculate_handler_specificity(
        self, handler_info: dict, request: Request, kwargs: dict
    ) -> int:
        """Calculate how specific/targeted this handler is for the current request."""
        sig = handler_info["signature"]
        method = handler_info["method"]
        params = list(sig.parameters.values())[1:]  # Skip 'self'

        type_hints = get_safe_type_hints(method, include_extras=True)

        score = 0
        injectable_params_with_data = 0

        for param in params:
            if param.name not in kwargs:
                continue

            param_analysis = self.analyzer.analyze_parameter(param, type_hints)
            score_increase = self._score_parameter_match(param_analysis, request)

            if score_increase >= 10:
                injectable_params_with_data += 1

            score += score_increase

        # Prefer handlers with more injectable parameters that have actual data
        score += injectable_params_with_data * 5
        return score

    def _score_parameter_match(self, param_analysis, request: Request) -> int:
        """Score how well a parameter matches the request data."""
        if param_analysis.injection_marker:
            return self._score_marker_match(param_analysis.injection_marker, request)

        # Low score for parameter defaults, medium score for container-injected parameters
        return 1 if param_analysis.has_default else 5

    def _score_marker_match(self, marker, request: Request) -> int:
        """Score how well an injection marker matches the request."""
        from serv.injectors import Cookie, Header, Query

        match marker:
            case Header(name) if (
                name in request.headers or name.lower() in request.headers
            ):
                return 10
            case Cookie(name) if name in request.cookies:
                return 10
            case Query(name) if name in request.query_params:
                return 10
            case Header(_, default) | Cookie(_, default) | Query(_, default) if (
                default is not None
            ):
                return 1
            case _:
                return 0

    async def extract_handler_parameters(
        self,
        handler_info: dict,
        request: Request,
        path_params: dict[str, Any],
        container: Container,
    ) -> dict:
        """Extract and prepare parameters for handler invocation."""
        sig = handler_info["signature"]
        method = handler_info["method"]
        params = list(sig.parameters.values())[1:]  # Skip 'self'
        kwargs = {}

        # Cache type hints to avoid repeated evaluation
        if not hasattr(self, '_type_hints_cache'):
            self._type_hints_cache = {}

        cache_key = id(method)
        if cache_key not in self._type_hints_cache:
            self._type_hints_cache[cache_key] = get_safe_type_hints(method, include_extras=True)
        type_hints = self._type_hints_cache[cache_key]

        for param in params:
            value = await self._extract_single_parameter(
                param, type_hints, request, path_params, container
            )

            if value is not None:
                kwargs[param.name] = value
            elif not self.extractor.parameter_has_fallback(param, type_hints):
                raise ValueError(
                    f"Required parameter '{param.name}' cannot be satisfied"
                )

        return kwargs

    async def _extract_single_parameter(
        self,
        param,
        type_hints: dict,
        request: Request,
        path_params: dict,
        container: Container,
    ) -> Any:
        """Extract a single parameter value from various sources."""
        param_analysis = self.analyzer.analyze_parameter(param, type_hints)

        # Try injection markers first
        if param_analysis.injection_marker:
            value = self.extractor.extract_from_marker(
                param_analysis.injection_marker, request
            )
            if value is not None:
                return value

        # Try path parameters (validate input)
        if param.name in path_params and path_params is not None:
            value = path_params.get(param.name)
            # Basic validation to prevent injection attacks
            if isinstance(value, str) and len(value) > 10000:  # Reasonable URL length limit
                raise ValueError(f"Path parameter '{param.name}' too long")
            return value

        # Try container injection for request types
        param_annotation = type_hints.get(param.name, param.annotation)
        if param_annotation is None:
            return None
        return await self.extractor.try_container_injection(
            param_annotation, request, container
        )

    async def try_single_handler(
        self,
        handler_info: dict,
        request: Request,
        path_params: dict,
        container: Container,
        has_form_handlers: bool,
    ) -> MethodHandlerResult:
        """Try a single method handler."""
        try:
            kwargs = await self.extract_handler_parameters(
                handler_info, request, path_params, container
            )
            return MethodHandlerResult(handler_info["method"], handler_info, kwargs)
        except AnnotationEvaluationError:
            # User code error in type annotations - propagate immediately
            raise
        except Exception as e:
            if not has_form_handlers:
                exc = HTTPBadRequestException(
                    f"Missing required parameters for {request.method} request: {e}"
                )
            else:
                exc = HTTPMethodNotAllowedException(
                    f"No compatible handler found for {request.method} request.",
                    list(
                        self.route.__method_handlers__.keys()
                        | self.route.__form_handlers__.keys()
                    ),
                )

            raise exc from e

    async def try_multiple_handlers(
        self,
        handlers: list,
        request: Request,
        path_params: dict,
        container: Container,
        has_form_handlers: bool,
    ) -> MethodHandlerResult:
        """Try multiple method handlers and select the best match."""
        compatible_handlers = []

        for handler_info in handlers:
            try:
                kwargs = await self.extract_handler_parameters(
                    handler_info, request, path_params, container
                )
                score = self.calculate_handler_specificity(
                    handler_info, request, kwargs
                )
                compatible_handlers.append((score, handler_info, kwargs))
            except AnnotationEvaluationError:
                # User code error in type annotations - propagate immediately
                raise
            except ValueError:
                # Expected: parameter cannot be satisfied - continue to next handler
                continue

        if not compatible_handlers:
            if not has_form_handlers:
                raise HTTPBadRequestException(
                    f"Missing required parameters for {request.method} request."
                )
            else:
                raise HTTPMethodNotAllowedException(
                    f"No compatible handler found for {request.method} request.",
                    list(
                        self.route.__method_handlers__.keys()
                        | self.route.__form_handlers__.keys()
                    ),
                )

        # Sort by score and take the best match
        compatible_handlers.sort(key=lambda x: x[0], reverse=True)
        score, selected_handler_info, kwargs = compatible_handlers[0]
        return MethodHandlerResult(
            selected_handler_info["method"], selected_handler_info, kwargs
        )


class ResponseProcessor:
    """Processes handler outputs into proper Response objects."""

    def __init__(self, route_instance):
        self.route = route_instance

    async def create_response(
        self, handler_output: Any, handler_info: dict, request: Request
    ) -> Response:
        """Create a Response from handler output."""
        handler_name = handler_info.get("name")

        if isinstance(handler_output, Response):
            return handler_output

        if self._has_response_wrapper(handler_name):
            return self._wrap_with_annotation(handler_output, handler_name)

        # Raw data without wrapper - this is an error
        raise self._create_response_error(handler_output, handler_name, request)

    def _has_response_wrapper(self, handler_name: str) -> bool:
        """Check if handler has an annotated response wrapper."""
        return (
            handler_name and handler_name in self.route.__annotated_response_wrappers__
        )

    def _wrap_with_annotation(self, data: Any, handler_name: str) -> Response:
        """Wrap data with annotated response wrapper."""
        wrapper_class = self.route.__annotated_response_wrappers__[handler_name]

        match data:
            case tuple() if all(isinstance(item, str | int | float | bool | type(None)) for item in data):
                return wrapper_class(*data)
            case _:
                return wrapper_class(data)

    def _create_response_error(
        self, handler_output: Any, handler_name: str, request: Request
    ) -> TypeError:
        """Create a detailed error for invalid response types."""
        handler_class = type(self.route).__name__
        handler_module = type(self.route).__module__

        # Get handler source info
        handler_file = "unknown"
        handler_line = "unknown"
        try:
            if handler_name and hasattr(self.route, handler_name):
                handler_method = getattr(self.route, handler_name)
                handler_source = inspect.getsourcefile(handler_method)
                handler_lines = inspect.getsourcelines(handler_method)
                if handler_source:
                    handler_file = handler_source
                if handler_lines:
                    handler_line = handler_lines[1]
        except (OSError, TypeError, AttributeError):
            # Expected failures during introspection - use safe defaults
            handler_file = "<unknown>"
            handler_line = "<unknown>"

        # Check if handler should have wrapper
        should_have_wrapper, wrapper_info = self._check_missing_wrapper(handler_name)

        if should_have_wrapper:
            error_msg = (
                f"Route handler has annotated response type but wrapper was not applied:\n"
                f"  Handler: {handler_class}.{handler_name}()\n"
                f"  Module: {handler_module}\n"
                f"  File: {handler_file}\n"
                f"  Line: {handler_line}\n"
                f"  Route: {request.method} '{request.path}'\n"
                f"  Returned: {type(handler_output).__name__!r}\n"
                f"  Expected wrapper: {wrapper_info}\n"
                f"  Issue: Annotated response wrapper was not applied (framework bug)"
            )
        else:
            error_msg = (
                f"Route handler returned wrong type:\n"
                f"  Handler: {handler_class}.{handler_name}()\n"
                f"  Module: {handler_module}\n"
                f"  File: {handler_file}\n"
                f"  Line: {handler_line}\n"
                f"  Route: {request.method} '{request.path}'\n"
                f"  Returned: {type(handler_output).__name__!r}\n"
                f"  Expected: Response instance or use an Annotated response type"
            )

        return TypeError(error_msg)

    def _check_missing_wrapper(self, handler_name: str) -> tuple[bool, str]:
        """Check if a handler should have had a response wrapper."""
        if not handler_name or not hasattr(self.route, handler_name):
            return False, ""

        try:
            from typing import Annotated, get_args, get_origin, get_type_hints

            handler_method = getattr(self.route, handler_name)
            type_hints = get_type_hints(handler_method, include_extras=True)
            return_annotation = type_hints.get("return")
        except Exception:
            return False, ""

        if return_annotation and get_origin(return_annotation) is Annotated:
            annotation_args = get_args(return_annotation)
            if (
                len(annotation_args) == 2
                and isinstance(annotation_args[1], type)
                and issubclass(annotation_args[1], Response)
            ):
                response_wrapper_class = annotation_args[1]
                return (
                    True,
                    f" (should be wrapped in {response_wrapper_class.__name__})",
                )

        return False, ""
