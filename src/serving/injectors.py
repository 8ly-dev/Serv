from typing import Annotated, get_args, get_origin, TypeAliasType

from bevy import Container
from bevy.hooks import hooks
from starlette.requests import Request
from tramp.optionals import Optional

from serving.config import Config, ConfigModel

type Cookie[T] = T
type Header[T] = T
type PathParam[T] = T
type QueryParam[T] = T


def is_annotated(dependency: type, expected_type: TypeAliasType) -> bool:
    return get_origin(dependency) is Annotated and get_origin(get_args(dependency)[0]) is expected_type


@hooks.HANDLE_UNSUPPORTED_DEPENDENCY
def handle_config_model_types(container: Container, dependency: type) -> Optional:
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
        # Key not found in config
        if is_collection:
            # Return empty list for collections when key is missing
            return Optional.Some([])
        else:
            # For single models, return Nothing so DI can try other sources
            return Optional.Nothing()


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
    return Optional.Some(request.cookies.get(name))


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
    return Optional.Some(request.headers.get(name))


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
    return Optional.Some(request.query_params.get(name))


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
    return Optional.Some(request.path_params.get(name))

