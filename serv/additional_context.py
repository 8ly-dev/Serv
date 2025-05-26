from collections.abc import Callable


class ExceptionContext:
    """
    Context manager for adding additional context to exceptions.

    This can be used to add notes or perform additional actions when an exception is raised within the context.

    Example:
        with ExceptionContext(ValueError).apply_note("Additional context"):
            raise ValueError("Original error message")

    Example:
        with ExceptionContext().capture(lambda exc: print(f"Captured: {exc}")):
            raise ValueError("Original error message")

    Example:
        with ExceptionContext(ValueError).capture(lambda exc: print(f"Captured: {exc}")).apply_note("Additional
        context"):
            raise ValueError("Original error message")
    """

    def __init__(self, exception: type[Exception] = Exception):
        self.exception_type = exception
        self.capture_callback = None
        self.note = None

    def apply_note(self, note: str):
        self.note = note
        return self

    def capture(self, callback: Callable[[Exception], None]):
        self.capture_callback = callback
        return self

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type and issubclass(exc_type, self.exception_type):
            exc_value.add_note(self.note)
            if self.capture_callback:
                self.capture_callback(exc_value)
