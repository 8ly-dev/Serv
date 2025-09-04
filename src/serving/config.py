import re
from pathlib import Path
from typing import Any, ClassVar, Literal, overload

import yaml


class Config:
    def __init__(self, config: dict):
        self.config = config

    @overload
    def get(self, key: str) -> dict[str, Any]: ...

    @overload
    def get[T](self, key: str, model: type[T]) -> T: ...

    @overload
    def get[T](self, key: str, model: type[T], is_collection: Literal[True]) -> list[T]: ...

    def get[T](self, key: str, model: type[T] | None = None, is_collection: bool = False) -> dict[str, Any] | T | list[T]:
        if not model:
            return self.config.get(key, [] if is_collection else {})

        if is_collection:
            return [
                self._construct(model, config)
                for config in self.config.get(key, [])
            ]

        return self._construct(model, self.config.get(key, {}))

    def _construct[T](self, model: type[T], config: dict) -> T:
        if hasattr(model, "from_dict"):
            return model.from_dict(config)

        return model(**config)

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


class ConfigModel:
    __model_key__: ClassVar[str]
    __is_collection__: ClassVar[bool] = False

    def __init_subclass__(cls, **kwargs):
        cls.__model_key__ = kwargs.pop("model_key", cls.__name__)
        cls.__is_collection__ = kwargs.pop("is_collection", False)
        super().__init_subclass__(**kwargs)

    @classmethod
    def __get_file_name_from_class_name(cls) -> str:
        """Converts a class name (ExampleClass) to a file name (example-class.yaml) using kebab case."""
        kebab_case = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", cls.__name__).lower()
        return f"{kebab_case}.yaml"
