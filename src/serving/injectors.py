import asyncio
import inspect
from typing import Annotated, get_args, get_origin, TypeAliasType

from bevy import Container
from bevy.hooks import hooks
from starlette.requests import Request
from tramp.optionals import Optional

from serving.config import Config, ConfigModel
from serving.forms import Form
from serving.session import Session, SessionConfig

type Cookie[T] = T
type Header[T] = T
type PathParam[T] = T
type QueryParam[T] = T
type SessionParam[T] = T


def is_annotated(dependency: type, expected_type: TypeAliasType) -> bool:
    return get_origin(dependency) is Annotated and get_origin(get_args(dependency)[0]) is expected_type


def get_parameter_default(context: dict):
    """Extract the parameter default value from the injection context.
    
    Returns the unwrapped default value if it exists, otherwise None.
    """
    if "injection_context" not in context:
        return None
    
    parameter_default = getattr(context["injection_context"], "parameter_default", Optional.Nothing())
    
    # Unwrap the Optional
    match parameter_default:
        case Optional.Some(value):
            return value
        case _:
            return None


@hooks.HANDLE_UNSUPPORTED_DEPENDENCY
def handle_config_model_types(container: Container, dependency: type, context: dict) -> Optional:
    must_be_collection = False
    if get_origin(dependency) is list:
        dependency = get_args(dependency)[0]
        must_be_collection = True

    try:
        if not issubclass(dependency, ConfigModel):
            return Optional.Nothing()
    except (TypeError, AttributeError):
        # Not a class or not a subclass of Model
        return Optional.Nothing()

    # Check for collection mismatch
    is_collection = getattr(dependency, "__is_collection__", False)

    if must_be_collection and not is_collection:
        raise ValueError(f"Dependency {dependency} is a singular value, but the injection expects a collection.")

    if not must_be_collection and is_collection:
        raise ValueError(f"Dependency {dependency} is a collection, but the injection expects a singular value.")

    # It's a Model subclass, try to get and instantiate it
    config = container.get(Config)
    try:
        model_instance = config.get(dependency.__model_key__, dependency, is_collection=is_collection)
        return Optional.Some(model_instance)
    except KeyError:
        # Key not found in config - check for default value
        default = get_parameter_default(context)
        if default is not None:
            return Optional.Some(default)
        
        # No default value available
        if is_collection:
            # Return empty list for collections when key is missing and no default
            return Optional.Some([])
        else:
            # For single models, return None when no default exists
            return Optional.Some(None)


@hooks.HANDLE_UNSUPPORTED_DEPENDENCY
def handle_cookie_types(container: Container, dependency: type, context: dict) -> Optional:
    name = context["injection_context"].parameter_name if "injection_context" in context else None
    if is_annotated(dependency, Cookie):
        dependency, name = get_args(dependency)

    elif get_origin(dependency) is not Cookie:
        return Optional.Nothing()

    if name is None:
        raise ValueError(f"Missing name for Cookie dependency: {dependency}")

    request = container.get(Request)
    value = request.cookies.get(name)
    
    if value is None:
        # Check for default value
        default = get_parameter_default(context)
        return Optional.Some(default)  # Return default or None

    return Optional.Some(value)


@hooks.HANDLE_UNSUPPORTED_DEPENDENCY
async def handle_form_types(container: Container, dependency: type, context: dict) -> Optional:
    try:
        if not issubclass(dependency, Form):
            return Optional.Nothing()
    except (TypeError, AttributeError):
        return Optional.Nothing()

    instance = await container.call(dependency.from_request)
    container.add(dependency, instance)
    return Optional.Some(instance)


@hooks.HANDLE_UNSUPPORTED_DEPENDENCY
async def handle_session_types(container: Container, dependency: type, context: dict) -> Optional:
    try:
        if not issubclass(dependency, Session):
            return Optional.Nothing()
    except (TypeError, AttributeError):
        return Optional.Nothing()

    # Build or load the request session via classmethod
    instance = await container.call(dependency.load_session)
    container.add(dependency, instance)
    return Optional.Some(instance)



@hooks.HANDLE_UNSUPPORTED_DEPENDENCY
def handle_header_types(container: Container, dependency: type, context: dict) -> Optional:
    name = context["injection_context"].parameter_name if "injection_context" in context else None
    if is_annotated(dependency, Header):
        dependency, name = get_args(dependency)

    elif get_origin(dependency) is not Header:
        return Optional.Nothing()

    if name is None:
        raise ValueError(f"Missing name for Header dependency: {dependency}")

    request = container.get(Request)
    value = request.headers.get(name)
    
    if value is None:
        # Check for default value
        default = get_parameter_default(context)
        return Optional.Some(default)  # Return default or None
    
    return Optional.Some(value)


@hooks.HANDLE_UNSUPPORTED_DEPENDENCY
def handle_session_param_types(container: Container, dependency: type, context: dict) -> Optional:
    name = context["injection_context"].parameter_name if "injection_context" in context else None
    if is_annotated(dependency, SessionParam):
        dependency, name = get_args(dependency)
    else:
        origin = get_origin(dependency)
        if origin is SessionParam:
            # Using SessionParam[T] without Annotated override
            pass
        elif origin is Annotated:
            # Support Annotated[T, SessionParam, "name"] style
            args = get_args(dependency)
            meta = args[1:]
            if any(m is SessionParam for m in meta):
                # Extract optional explicit key override from metadata
                for m in meta:
                    if isinstance(m, str):
                        name = m
                        break
            else:
                return Optional.Nothing()
        else:
            return Optional.Nothing()

    if name is None:
        raise ValueError(f"Missing name for SessionParam dependency: {dependency}")

    # Determine the configured Session type (default to base Session)
    try:
        session_config = container.get(SessionConfig)
        session_type = session_config.session_type or Session
    except Exception:
        session_type = Session

    # Ensure session instance exists in container
    session_instance = container.get(session_type)
    if name in session_instance:  # type: ignore[operator]
        return Optional.Some(session_instance[name])  # type: ignore[index]

    default = get_parameter_default(context)
    return Optional.Some(default)


@hooks.HANDLE_UNSUPPORTED_DEPENDENCY
def handle_query_param_types(container: Container, dependency: type, context: dict) -> Optional:
    name = context["injection_context"].parameter_name if "injection_context" in context else None
    if is_annotated(dependency, QueryParam):
        dependency, name = get_args(dependency)

    elif get_origin(dependency) is not QueryParam:
        return Optional.Nothing()

    if name is None:
        raise ValueError(f"Missing name for QueryParam dependency: {dependency}")

    request = container.get(Request)
    value = request.query_params.get(name)
    
    if value is None:
        # Check for default value
        default = get_parameter_default(context)
        return Optional.Some(default)  # Return default or None
    
    return Optional.Some(value)


@hooks.HANDLE_UNSUPPORTED_DEPENDENCY
def handle_path_param_types(container: Container, dependency: type, context: dict) -> Optional:
    name = context["injection_context"].parameter_name if "injection_context" in context else None
    if is_annotated(dependency, PathParam):
        dependency, name = get_args(dependency)

    elif get_origin(dependency) is not PathParam:
        return Optional.Nothing()

    if name is None:
        raise ValueError(f"Missing name for PathParam dependency: {dependency}")

    request = container.get(Request)
    value = request.path_params.get(name)
    
    if value is None:
        # Check for default value
        default = get_parameter_default(context)
        return Optional.Some(default)  # Return default or None
    
    return Optional.Some(value)
