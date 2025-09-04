from typing import Any

import yaml
from bevy.registries import Registry
from starlette.applications import Starlette


class Serv:
    def __init__(self, config_path: str | None = None):
        self.app = Starlette()
        self.registry = Registry()
        self.container = self.registry.create_container()
        self.config: dict[str, Any] = {}

        if config_path:
            self.load_config(config_path)

    def load_config(self, config_path: str) -> None:
        with open(config_path) as f:
            self.config = yaml.safe_load(f) or {}
