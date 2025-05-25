from typing import overload, Type


class AdditionalExceptionContext:
    """
    Context manager that adds additional context to an exception if it is raised within the context.

    Args:
        exception_type: The type of exception to add context to. Defaults to Exception.
        message: The message to add to the exception.

    Usage:
        with AdditionalExceptionContext(ValueError, "Additional context"):
            raise ValueError("Original error message")

        # ValueError will be raised with the message: "Additional context\nOriginal error message"

    Usage:
        with AdditionalExceptionContext("Additional context"):
            raise RuntimeError("Original error message")

        # Exception will be raised with the message: "Additional context\nOriginal error message"
    """
    @overload
    def __init__(self, exception_type: type[Exception], message: str):
        ...

    @overload
    def __init__(self, message: str):
        ...

    def __init__(self, *args: str | Type[Exception]):
        match args:
            case [Exception() as exception_type, str() as message]:
                self.exception_type = exception_type
                self.message = message
            case [str() as message]:
                self.exception_type = Exception
                self.message = message
            case _:
                raise ValueError(f"Invalid arguments for AdditionalExceptionContext: {args}")

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type and issubclass(exc_type, self.exception_type):
            exc_value.add_note(self.message)
