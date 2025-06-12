"""Parameter analysis and injection utilities for route handlers."""

import inspect
import logging
from typing import Any

from bevy.containers import Container
from bevy import DependencyResolutionError

from ..http.requests import Request
from ..injectors import Cookie, Header, Query
from ..utils.type_utils import extract_annotated_info

logger = logging.getLogger(__name__)


class ParameterAnalysis:
    """Results of analyzing a handler parameter."""

    def __init__(
        self,
        name: str,
        annotation: Any,
        default: Any,
        has_default: bool,
        injection_marker: Header | Cookie | Query | None = None,
    ):
        self.name = name
        self.annotation = annotation
        self.default = default
        self.has_default = has_default
        self.injection_marker = injection_marker
        
        # Validate injection marker if present
        if injection_marker is not None:
            self._validate_injection_marker(injection_marker)
    
    def _validate_injection_marker(self, marker: Header | Cookie | Query) -> None:
        """Validate an injection marker has valid configuration."""
        if not marker.name or not isinstance(marker.name, str):
            raise ValueError(f"Injection marker name must be a non-empty string, got: {marker.name}")
        
        if marker.name.strip() != marker.name:
            raise ValueError(f"Injection marker name cannot have leading/trailing whitespace: '{marker.name}'")
        
        # Additional validation for specific marker types
        if isinstance(marker, Header):
            # HTTP header names should be printable ASCII
            if not marker.name.isascii() or not marker.name.isprintable():
                raise ValueError(f"Header name must be printable ASCII: '{marker.name}'")


class ParameterAnalyzer:
    """Analyzes handler parameters for injection and scoring."""

    @staticmethod
    def analyze_parameter(param, type_hints: dict) -> ParameterAnalysis:
        """Analyze a single parameter and its injection requirements."""
        param_annotation = type_hints.get(param.name, param.annotation)
        base_type, metadata = extract_annotated_info(param_annotation)

        injection_marker = None
        if metadata and isinstance(metadata, Header | Cookie | Query):
            injection_marker = metadata

        return ParameterAnalysis(
            name=param.name,
            annotation=param.annotation,
            default=param.default,
            has_default=param.default != param.empty,
            injection_marker=injection_marker,
        )

    @staticmethod
    def score_injectable_parameter(
        marker: Header | Cookie | Query,
        param_analysis: ParameterAnalysis,
        request: Request,
    ) -> int:
        """Score an injectable parameter based on data availability."""
        match marker:
            case Header(name) if name in request.headers:
                return 10
            case Cookie(name) if name in request.cookies:
                return 10
            case Query(name) if name in request.query_params:
                return 10
            case Header(_, default) | Cookie(_, default) | Query(_, default) if (
                default is not None
            ):
                return 5
            case _ if param_analysis.has_default:
                return 5
            case _:
                return -5

    @staticmethod
    def score_regular_parameter(param_analysis: ParameterAnalysis) -> int:
        """Score a regular (non-injectable) parameter."""
        return 1 if param_analysis.has_default else -2


class ParameterExtractor:
    """Extracts parameter values from requests and containers."""
    
    # Cache for Request type checking to improve performance
    _request_type_cache: dict[type, bool] = {}

    @staticmethod
    def extract_from_marker(marker: Header | Cookie | Query, request: Request) -> Any:
        """Extract value using an injection marker."""
        match marker:
            case Header(name, default):
                header_value = request.headers.get(name) or request.headers.get(
                    name.lower()
                )
                return header_value if header_value is not None else default
            case Cookie(name, default):
                return request.cookies.get(name, default)
            case Query(name, default):
                return request.query_params.get(name, default)
            case _:
                return None

    @staticmethod
    async def try_container_injection(
        injection_type, request: Request, container: Container
    ) -> Any:
        """Try to inject a parameter from the container."""
        # Extract actual type if it's Annotated
        base_type, _ = extract_annotated_info(injection_type)
        if base_type:
            injection_type = base_type

        # Handle request types
        if injection_type is not type(None) and ParameterExtractor._is_request_type(injection_type):
            try:
                return injection_type(request.scope, request._receive)
            except Exception as e:
                # Log but don't raise - this allows fallback to container injection
                logger.debug(f"Failed to create request type {injection_type.__name__}: {e}")

        # Try container injection with specific error handling
        try:
            return container.get(injection_type)
        except (DependencyResolutionError, KeyError, TypeError, AttributeError) as e:
            # These are expected errors when type is not available in container
            logger.debug(f"Container injection failed for {injection_type}: {e}")
            return None
        except Exception as e:
            # Log unexpected errors but don't crash
            logger.warning(f"Unexpected error during container injection for {injection_type}: {e}")
            return None

    @staticmethod
    def _is_request_type(injection_type: type) -> bool:
        """Check if a type is a Request subclass with caching for performance."""
        # Check cache first
        if injection_type in ParameterExtractor._request_type_cache:
            return ParameterExtractor._request_type_cache[injection_type]
        
        # Perform the check
        is_request = (
            inspect.isclass(injection_type) and 
            issubclass(injection_type, Request) and
            injection_type is not Request  # Don't allow base Request class
        )
        
        # Cache the result
        ParameterExtractor._request_type_cache[injection_type] = is_request
        return is_request

    @staticmethod
    def parameter_has_fallback(param, type_hints: dict) -> bool:
        """Check if a parameter has a fallback value."""
        if param.default != param.empty:
            return True

        param_annotation = type_hints.get(param.name, param.annotation)
        _, metadata = extract_annotated_info(param_annotation)

        if (
            metadata
            and isinstance(metadata, Header | Cookie | Query)
            and metadata.default is not None
        ):
            return True

        return False
