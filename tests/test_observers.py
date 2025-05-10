from typing import Annotated
from bevy import dependency, get_container
import pytest

from serv.observers import Observer


class _TestUser:
    def __init__(self, user_id: int, user_name: str):
        self.user_id = user_id
        self.user_name = user_name


@pytest.mark.asyncio
async def test_observers():
    class TestObserver(Observer):
        async def on_user_create(
            self,
            user: _TestUser = dependency(),
        ):
            assert user.user_id == 1
            assert user.user_name == "John Doe"

    container = get_container().branch()
    container.instances[_TestUser] = _TestUser(1, "John Doe")
    await TestObserver().on("user_create", container)


@pytest.mark.asyncio
async def test_observers_with_args():    
    class TestObserver(Observer):
        async def on_user_create(
            self,
            user: _TestUser = dependency(),
        ):
            assert user.user_id == 2
            assert user.user_name == "Jane Doe"

    container = get_container().branch()
    container.instances[_TestUser] = _TestUser(1, "John Doe")
    await TestObserver().on("user_create", container, user=_TestUser(2, "Jane Doe"))


@pytest.mark.asyncio
async def test_observers_with_args_and_dependency():
    class TestObserver(Observer):
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
    await TestObserver().on("user_create", container, user_name="John Doe")


@pytest.mark.asyncio
async def test_observers_without_handler():
    class TestObserver(Observer):
        ...

    await TestObserver().on("user_create")


@pytest.mark.asyncio
async def test_observers_with_multiple_handlers():
    reached_handlers = set()

    class TestObserver(Observer):
        async def a_on_user_create(self):
            reached_handlers.add("a_on_user_create")

        async def b_on_user_create(self):
            reached_handlers.add("b_on_user_create")

    
    await TestObserver().on("user_create")
    assert reached_handlers == {"a_on_user_create", "b_on_user_create"}


@pytest.mark.asyncio
async def test_observers_with_unfilled_dependency():
    class TestObserver(Observer):
        async def on_user_create(
            self,
            user: _TestUser = dependency(),
        ):
            ...
        
    with pytest.raises(TypeError):
        await TestObserver().on("user_create")  
