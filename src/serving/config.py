import re
from pathlib import Path
from typing import Any, ClassVar

from bevy import hooks
from bevy.containers import Container, Optional
from bevy.hooks import Hook
import yaml


class Config:
    def __init__(self, config: dict):
        self.config = config

    def get[T: dict](self, key: str, model: type[T] | None = None) -> T:
        if model:
            return model(**self.config[key])

        return self.config[key]

    @classmethod
    def load_config(cls, name: str, directory: str = ".") -> "Config":
        match directory:
            case ".":
                path = Path()

            case str():
                path = Path(directory)

            case Path():
                path = directory

            case _:
                raise ValueError(f"Invalid directory: {directory}")

        file_path = path / name
        with file_path.open("r") as f:
            return Config(yaml.safe_load(f))


class Model:
    __model_key__: ClassVar[str]

    def __init_subclass__(cls, **kwargs):
        cls.__model_key__ = kwargs.pop("model_key", cls.__name__)
        super().__init_subclass__(**kwargs)

    @classmethod
    def __get_file_name_from_class_name(cls) -> str:
        """Converts a class name (ExampleClass) to a file name (example-class.yaml) using kebab case."""
        kebab_case = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", cls.__name__).lower()
        return f"{kebab_case}.yaml"


@hooks.hooks(Hook.HANDLE_UNSUPPORTED_DEPENDENCY)
def handle_model_types(container: Container, dependency: type, context: dict[str, Any]) -> Optional:
    try:
        if not issubclass(dependency, Model):
            return Optional.Nothing()
    except (TypeError, AttributeError):
        # Not a class or not a subclass of Model
        return Optional.Nothing()
    
    # It's a Model subclass, try to get and instantiate it
    config = container.get(Config)
    model_instance = config.get(dependency.__model_key__, dependency)
    return Optional.Some(model_instance)
