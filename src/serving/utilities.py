from functools import wraps

import bevy.injection_types
from bevy import get_container

import serving.response


class RequestLifecycleNotStarted(Exception):
    pass


def ensure_request_lifecycle(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            get_container().get(serving.response.ServResponse)
        except bevy.injection_types.DependencyResolutionError:
            raise RequestLifecycleNotStarted(
                f"'{func.__module__}.{func.__qualname__}' cannot be used outside of a request."
            ) from None

        return func(*args, **kwargs)

    return wrapper
