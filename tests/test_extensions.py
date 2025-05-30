import sys

import pytest
from bevy import dependency, get_container

from serv.extensions import Extension, on
from tests.helpers import create_test_extension_spec


class _TestUser:
    def __init__(self, user_id: int, user_name: str):
        self.user_id = user_id
        self.user_name = user_name


@pytest.mark.asyncio
async def test_extensions():
    class TestExtension(Extension):
        @on("user_create")
        async def handle_user_create(
            self,
            user: _TestUser = dependency(),
        ):
            assert user.user_id == 1
            assert user.user_name == "John Doe"

    container = get_container().branch()
    container.instances[_TestUser] = _TestUser(1, "John Doe")

    # Patch the module for this locally defined TestExtension
    test_extension_module = sys.modules[TestExtension.__module__]
    original_spec = getattr(test_extension_module, "__extension_spec__", None)
    # Create a minimal spec, as these plugins don't rely on extension.yaml content here
    spec = create_test_extension_spec(name="LocalTestExtension", version="0.0.0")
    test_extension_module.__extension_spec__ = spec

    plugin_instance = TestExtension(stand_alone=True)  # stand_alone still good practice
    plugin_instance.__extension_spec__ = (
        spec  # Set on instance too if anything might check
    )

    await plugin_instance.on("user_create", container=container)

    # Clean up module patch
    if original_spec is not None:
        test_extension_module.__extension_spec__ = original_spec
    elif hasattr(test_extension_module, "__extension_spec__"):
        del test_extension_module.__extension_spec__


@pytest.mark.asyncio
async def test_extensions_with_args():
    class TestExtension(Extension):
        @on("user_create")
        async def handle_user_create(
            self,
            user: _TestUser = dependency(),
        ):
            assert user.user_id == 2
            assert user.user_name == "Jane Doe"

    container = get_container().branch()
    container.instances[_TestUser] = _TestUser(1, "John Doe")

    test_extension_module = sys.modules[TestExtension.__module__]
    original_spec = getattr(test_extension_module, "__extension_spec__", None)
    spec = create_test_extension_spec(name="LocalTestExtensionArgs", version="0.0.0")
    test_extension_module.__extension_spec__ = spec

    plugin_instance = TestExtension(stand_alone=True)
    plugin_instance.__extension_spec__ = spec

    await plugin_instance.on("user_create", container, user=_TestUser(2, "Jane Doe"))

    if original_spec is not None:
        test_extension_module.__extension_spec__ = original_spec
    elif hasattr(test_extension_module, "__extension_spec__"):
        del test_extension_module.__extension_spec__


@pytest.mark.asyncio
async def test_extensions_with_args_and_dependency():
    class TestExtension(Extension):
        @on("user_create")
        async def handle_user_create(
            self,
            user_name: str,
            user: _TestUser = dependency(),
        ):
            assert user.user_id == 1
            assert user.user_name == "John Doe"
            assert user_name == "John Doe"

    container = get_container().branch()
    container.instances[_TestUser] = _TestUser(1, "John Doe")

    test_extension_module = sys.modules[TestExtension.__module__]
    original_spec = getattr(test_extension_module, "__extension_spec__", None)
    spec = create_test_extension_spec(name="LocalTestExtensionDep", version="0.0.0")
    test_extension_module.__extension_spec__ = spec

    plugin_instance = TestExtension(stand_alone=True)
    plugin_instance.__extension_spec__ = spec

    await plugin_instance.on("user_create", container, user_name="John Doe")

    if original_spec is not None:
        test_extension_module.__extension_spec__ = original_spec
    elif hasattr(test_extension_module, "__extension_spec__"):
        del test_extension_module.__extension_spec__


@pytest.mark.asyncio
async def test_extensions_without_handler():
    class TestExtension(Extension): ...

    test_extension_module = sys.modules[TestExtension.__module__]
    original_spec = getattr(test_extension_module, "__extension_spec__", None)
    spec = create_test_extension_spec(
        name="LocalTestExtensionNoHandler", version="0.0.0"
    )
    test_extension_module.__extension_spec__ = spec

    plugin_instance = TestExtension(stand_alone=True)
    plugin_instance.__extension_spec__ = spec

    await plugin_instance.on("user_create")

    if original_spec is not None:
        test_extension_module.__extension_spec__ = original_spec
    elif hasattr(test_extension_module, "__extension_spec__"):
        del test_extension_module.__extension_spec__


@pytest.mark.asyncio
async def test_extensions_with_multiple_handlers():
    reached_handlers = set()

    class TestExtension(Extension):
        @on("user_create")
        async def a_handle_user_create(self):
            reached_handlers.add("a_handle_user_create")

        @on("user_create")
        async def b_handle_user_create(self):
            reached_handlers.add("b_handle_user_create")

    test_extension_module = sys.modules[TestExtension.__module__]
    original_spec = getattr(test_extension_module, "__extension_spec__", None)
    spec = create_test_extension_spec(name="LocalTestExtensionMulti", version="0.0.0")
    test_extension_module.__extension_spec__ = spec

    plugin_instance = TestExtension(stand_alone=True)
    plugin_instance.__extension_spec__ = spec

    await plugin_instance.on("user_create")
    assert reached_handlers == {"a_handle_user_create", "b_handle_user_create"}

    if original_spec is not None:
        test_extension_module.__extension_spec__ = original_spec
    elif hasattr(test_extension_module, "__extension_spec__"):
        del test_extension_module.__extension_spec__


@pytest.mark.asyncio
async def test_extensions_with_unfilled_dependency():
    class TestExtension(Extension):
        @on("user_create")
        async def handle_user_create(
            self,
            user: _TestUser = dependency(),
        ): ...

    test_extension_module = sys.modules[TestExtension.__module__]
    original_spec = getattr(test_extension_module, "__extension_spec__", None)
    spec = create_test_extension_spec(
        name="LocalTestExtensionUnfilled", version="0.0.0"
    )
    test_extension_module.__extension_spec__ = spec

    plugin_instance = TestExtension(stand_alone=True)
    plugin_instance.__extension_spec__ = spec

    with pytest.raises(TypeError):
        await plugin_instance.on("user_create")

    if original_spec is not None:
        test_extension_module.__extension_spec__ = original_spec
    elif hasattr(test_extension_module, "__extension_spec__"):
        del test_extension_module.__extension_spec__
