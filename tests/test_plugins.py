import sys
from typing import Annotated
from bevy import dependency, get_container
import pytest

from serv.plugins import Plugin
from serv.plugins.loader import PluginSpec
from pathlib import Path
from tests.helpers import create_test_plugin_spec


class _TestUser:
    def __init__(self, user_id: int, user_name: str):
        self.user_id = user_id
        self.user_name = user_name


@pytest.mark.asyncio
async def test_plugins():
    class TestPlugin(Plugin):
        async def on_user_create(
            self,
            user: _TestUser = dependency(),
        ):
            assert user.user_id == 1
            assert user.user_name == "John Doe"

    container = get_container().branch()
    container.instances[_TestUser] = _TestUser(1, "John Doe")

    # Patch the module for this locally defined TestPlugin
    test_plugin_module = sys.modules[TestPlugin.__module__]
    original_spec = getattr(test_plugin_module, '__plugin_spec__', None)
    # Create a minimal spec, as these plugins don't rely on plugin.yaml content here
    spec = create_test_plugin_spec(name="LocalTestPlugin", version="0.0.0")
    test_plugin_module.__plugin_spec__ = spec

    plugin_instance = TestPlugin(stand_alone=True) # stand_alone still good practice
    plugin_instance.__plugin_spec__ = spec # Set on instance too if anything might check

    await plugin_instance.on("user_create", container)

    # Clean up module patch
    if original_spec is not None:
        test_plugin_module.__plugin_spec__ = original_spec
    elif hasattr(test_plugin_module, '__plugin_spec__'):
        del test_plugin_module.__plugin_spec__


@pytest.mark.asyncio
async def test_plugins_with_args():    
    class TestPlugin(Plugin):
        async def on_user_create(
            self,
            user: _TestUser = dependency(),
        ):
            assert user.user_id == 2
            assert user.user_name == "Jane Doe"

    container = get_container().branch()
    container.instances[_TestUser] = _TestUser(1, "John Doe")

    test_plugin_module = sys.modules[TestPlugin.__module__]
    original_spec = getattr(test_plugin_module, '__plugin_spec__', None)
    spec = create_test_plugin_spec(name="LocalTestPluginArgs", version="0.0.0")
    test_plugin_module.__plugin_spec__ = spec

    plugin_instance = TestPlugin(stand_alone=True)
    plugin_instance.__plugin_spec__ = spec

    await plugin_instance.on("user_create", container, user=_TestUser(2, "Jane Doe"))

    if original_spec is not None:
        test_plugin_module.__plugin_spec__ = original_spec
    elif hasattr(test_plugin_module, '__plugin_spec__'):
        del test_plugin_module.__plugin_spec__


@pytest.mark.asyncio
async def test_plugins_with_args_and_dependency():
    class TestPlugin(Plugin):
        async def on_user_create(
            self,
            user_name: str,
            user: _TestUser = dependency(),
        ):
            assert user.user_id == 1
            assert user.user_name == "John Doe"
            assert user_name == "John Doe"

    container = get_container().branch()
    container.instances[_TestUser] = _TestUser(1, "John Doe")

    test_plugin_module = sys.modules[TestPlugin.__module__]
    original_spec = getattr(test_plugin_module, '__plugin_spec__', None)
    spec = create_test_plugin_spec(name="LocalTestPluginDep", version="0.0.0")
    test_plugin_module.__plugin_spec__ = spec

    plugin_instance = TestPlugin(stand_alone=True)
    plugin_instance.__plugin_spec__ = spec

    await plugin_instance.on("user_create", container, user_name="John Doe")

    if original_spec is not None:
        test_plugin_module.__plugin_spec__ = original_spec
    elif hasattr(test_plugin_module, '__plugin_spec__'):
        del test_plugin_module.__plugin_spec__


@pytest.mark.asyncio
async def test_plugins_without_handler():
    class TestPlugin(Plugin):
        ...

    test_plugin_module = sys.modules[TestPlugin.__module__]
    original_spec = getattr(test_plugin_module, '__plugin_spec__', None)
    spec = create_test_plugin_spec(name="LocalTestPluginNoHandler", version="0.0.0")
    test_plugin_module.__plugin_spec__ = spec

    plugin_instance = TestPlugin(stand_alone=True)
    plugin_instance.__plugin_spec__ = spec

    await plugin_instance.on("user_create")

    if original_spec is not None:
        test_plugin_module.__plugin_spec__ = original_spec
    elif hasattr(test_plugin_module, '__plugin_spec__'):
        del test_plugin_module.__plugin_spec__


@pytest.mark.asyncio
async def test_plugins_with_multiple_handlers():
    reached_handlers = set()

    class TestPlugin(Plugin):
        async def a_on_user_create(self):
            reached_handlers.add("a_on_user_create")

        async def b_on_user_create(self):
            reached_handlers.add("b_on_user_create")

    test_plugin_module = sys.modules[TestPlugin.__module__]
    original_spec = getattr(test_plugin_module, '__plugin_spec__', None)
    spec = create_test_plugin_spec(name="LocalTestPluginMulti", version="0.0.0")
    test_plugin_module.__plugin_spec__ = spec

    plugin_instance = TestPlugin(stand_alone=True)
    plugin_instance.__plugin_spec__ = spec
    
    await plugin_instance.on("user_create")
    assert reached_handlers == {"a_on_user_create", "b_on_user_create"}

    if original_spec is not None:
        test_plugin_module.__plugin_spec__ = original_spec
    elif hasattr(test_plugin_module, '__plugin_spec__'):
        del test_plugin_module.__plugin_spec__


@pytest.mark.asyncio
async def test_plugins_with_unfilled_dependency():
    class TestPlugin(Plugin):
        async def on_user_create(
            self,
            user: _TestUser = dependency(),
        ):
            ...
        
    test_plugin_module = sys.modules[TestPlugin.__module__]
    original_spec = getattr(test_plugin_module, '__plugin_spec__', None)
    spec = create_test_plugin_spec(name="LocalTestPluginUnfilled", version="0.0.0")
    test_plugin_module.__plugin_spec__ = spec

    plugin_instance = TestPlugin(stand_alone=True)
    plugin_instance.__plugin_spec__ = spec

    with pytest.raises(TypeError):
        await plugin_instance.on("user_create")

    if original_spec is not None:
        test_plugin_module.__plugin_spec__ = original_spec
    elif hasattr(test_plugin_module, '__plugin_spec__'):
        del test_plugin_module.__plugin_spec__
