from dataclasses import dataclass
from typing import Any

import pytest

from serv.requests import Request


# Helper to simulate ASGI receive channel for form data
async def mock_receive_factory(form_data_bytes: bytes):
    is_consumed = False

    async def mock_receive():
        nonlocal is_consumed
        if not is_consumed:
            is_consumed = True
            return {"type": "http.request", "body": form_data_bytes, "more_body": False}
        return {"type": "http.request", "body": b"", "more_body": False}

    return mock_receive


async def create_request_with_form_data(
    form_data: dict | str,
    content_type: str = "application/x-www-form-urlencoded",
    method: str = "POST",
) -> Request:
    if isinstance(form_data, dict):
        parts = []
        for k, v_list_or_val in form_data.items():
            if isinstance(v_list_or_val, list):
                for v_item in v_list_or_val:
                    parts.append(f"{k}={v_item}")
            else:
                parts.append(f"{k}={v_list_or_val}")
        body_string = "&".join(parts)
        body_bytes = body_string.encode("utf-8")
    else:  # string, assumed to be already urlencoded
        body_bytes = form_data.encode("utf-8")

    scope = {
        "type": "http",
        "method": method,
        "headers": [(b"content-type", content_type.encode("latin-1"))],
        "path": "/testform",
        "query_string": b"",
    }
    actual_receive_callable = await mock_receive_factory(body_bytes)
    return Request(scope, actual_receive_callable)


# --- Test Models ---
@dataclass
class BasicTypesModel:
    name: str
    age: int
    height: float
    is_member: bool


@dataclass
class OptionalTypesModel:
    description: str | None = None
    count: int | None = None
    notes: str | None = "default_note"


@dataclass
class ListTypesModel:
    tags: list[str]
    scores: list[int]
    aliases: list
    ids: list[int] | None = None


@dataclass
class CoercionRulesModel:
    item_id: int
    categories: list[str]


@dataclass
class AllFieldsRequiredModel:
    field_a: str
    field_b: int


# --- Tests ---


@pytest.mark.asyncio
async def test_form_coercion_basic_types_correct():
    request = await create_request_with_form_data(
        {"name": "Alice", "age": "30", "height": "5.6", "is_member": "true"}
    )
    model_instance = await request.form(model=BasicTypesModel)
    assert isinstance(model_instance, BasicTypesModel)
    assert model_instance.name == "Alice"
    assert model_instance.age == 30
    assert model_instance.height == 5.6
    assert model_instance.is_member is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bool_val_str, expected_bool",
    [
        ("True", True),
        ("tRuE", True),
        ("on", True),
        ("1", True),
        ("yes", True),
        ("False", False),
        ("fAlSe", False),
        ("off", False),
        ("0", False),
        ("no", False),
    ],
)
async def test_form_coercion_boolean_variations(bool_val_str: str, expected_bool: bool):
    request = await create_request_with_form_data({"is_member": bool_val_str})

    @dataclass
    class BoolModel:
        is_member: bool

    model_instance = await request.form(model=BoolModel)
    assert model_instance.is_member == expected_bool


@pytest.mark.asyncio
async def test_form_coercion_basic_type_conversion_error():
    request = await create_request_with_form_data({"age": "not-an-int"})
    with pytest.raises(
        ValueError,
        match=r"Error coercing value 'not-an-int' for field 'age'.*invalid literal for int\(\) with base 10: 'not-an-int'",
    ):
        await request.form(model=BasicTypesModel)


@pytest.mark.asyncio
async def test_form_coercion_optional_types_present():
    request = await create_request_with_form_data(
        {"description": "test desc", "count": "101"}
    )
    model_instance = await request.form(model=OptionalTypesModel)
    assert model_instance.description == "test desc"
    assert model_instance.count == 101
    assert model_instance.notes == "default_note"


@pytest.mark.asyncio
async def test_form_coercion_optional_types_empty_string_becomes_none():
    request = await create_request_with_form_data({"description": "", "count": ""})
    model_instance = await request.form(model=OptionalTypesModel)
    assert model_instance.description is None
    assert model_instance.count is None


@pytest.mark.asyncio
async def test_form_coercion_optional_types_missing_from_form():
    request = await create_request_with_form_data({})
    model_instance = await request.form(model=OptionalTypesModel)
    assert model_instance.description is None
    assert model_instance.count is None
    assert model_instance.notes == "default_note"


@pytest.mark.asyncio
async def test_form_coercion_list_types_multiple_values():
    request = await create_request_with_form_data(
        {
            "tags": ["urgent", "review"],
            "scores": ["10", "20", "30"],
            "aliases": ["one", "two"],
        }
    )
    model_instance = await request.form(model=ListTypesModel)
    assert model_instance.tags == ["urgent", "review"]
    assert model_instance.scores == [10, 20, 30]
    assert model_instance.aliases == ["one", "two"]


@pytest.mark.asyncio
async def test_form_coercion_list_types_single_value():
    request = await create_request_with_form_data(
        {"tags": "urgent", "scores": "10", "aliases": "solo"}
    )
    model_instance = await request.form(model=ListTypesModel)
    assert model_instance.tags == ["urgent"]
    assert model_instance.scores == [10]
    assert model_instance.aliases == ["solo"]


@dataclass
class PartialListModel:
    tags: list[str]
    scores: list[int] | None = None
    aliases: list | None = None
    ids: list[int] | None = None


@pytest.mark.asyncio
async def test_form_coercion_list_types_empty_tag_value():
    request = await create_request_with_form_data("tags=")
    model_instance = await request.form(model=PartialListModel)
    assert model_instance.tags == [""]
    assert model_instance.scores is None


@dataclass
class StrictListModel:
    values: list[int]


@pytest.mark.asyncio
async def test_form_coercion_list_item_coercion_failure():
    request = await create_request_with_form_data({"values": ["1", "not-an-int", "3"]})
    with pytest.raises(
        ValueError,
        match=r"Error coercing item 'not-an-int' for field 'values'.*invalid literal for int\(\) with base 10: 'not-an-int'",
    ):
        await request.form(model=StrictListModel)


@dataclass
class CoercionRule1TestModel:
    item_id: int
    categories: list[str] | None = None


@pytest.mark.asyncio
async def test_form_coercion_rule1_refined():
    request = await create_request_with_form_data({"item_id": ["100", "200"]})
    model_instance = await request.form(model=CoercionRule1TestModel)
    assert model_instance.item_id == 100
    assert model_instance.categories is None


@dataclass
class CoercionRule2TestModel:
    categories: list[str]
    item_id: int | None = None


@pytest.mark.asyncio
async def test_form_coercion_rule2_single_for_list_field():
    request = await create_request_with_form_data({"categories": "alpha"})
    model_instance = await request.form(model=CoercionRule2TestModel)
    assert model_instance.categories == ["alpha"]


@pytest.mark.asyncio
async def test_form_coercion_model_instantiation_missing_required_field():
    request = await create_request_with_form_data({"field_a": "value_a"})
    with pytest.raises(
        TypeError,
        match=r"Failed to instantiate model AllFieldsRequiredModel.*__init__\(\) missing 1 required positional argument: 'field_b'",
    ):
        await request.form(model=AllFieldsRequiredModel)


@pytest.mark.asyncio
async def test_form_coercion_default_dict_behavior():
    form_data_dict = {"name": "Bob", "hobbies": ["cycling", "reading"]}
    request = await create_request_with_form_data(form_data_dict)
    result = await request.form()
    assert result == {"name": ["Bob"], "hobbies": ["cycling", "reading"]}


@pytest.mark.asyncio
async def test_form_coercion_empty_form_data_dict_model():
    request = await create_request_with_form_data({})
    result = await request.form(model=dict)
    assert result == {}


@pytest.mark.asyncio
async def test_form_coercion_empty_form_data_custom_model_optional_fields():
    request = await create_request_with_form_data({})
    model_instance = await request.form(model=OptionalTypesModel)
    assert isinstance(model_instance, OptionalTypesModel)
    assert model_instance.description is None
    assert model_instance.count is None
    assert model_instance.notes == "default_note"


@pytest.mark.asyncio
async def test_form_coercion_empty_form_data_custom_model_required_fields():
    request = await create_request_with_form_data({})
    with pytest.raises(
        TypeError,
        match=r"AllFieldsRequiredModel.__init__\(\) missing 2 required positional arguments: (?:\'field_a\' and \'field_b\'|\'field_b\' and \'field_a\')",
    ):
        await request.form(model=AllFieldsRequiredModel)


@pytest.mark.asyncio
async def test_form_coercion_invalid_content_type():
    request = await create_request_with_form_data({}, content_type="application/json")
    with pytest.raises(
        RuntimeError, match="Cannot parse form data for Content-Type 'application/json'"
    ):
        await request.form(model=BasicTypesModel)


@pytest.mark.asyncio
async def test_form_coercion_unsupported_target_type_in_model():
    class NonStringConstructible:
        def __init__(self, num_str: str):
            self.num = int(num_str)

    @dataclass
    class WillFailModel:
        complex_field: NonStringConstructible

    request_fail = await create_request_with_form_data({"complex_field": "wont_work"})
    with pytest.raises(
        ValueError,
        match=r"Error coercing value 'wont_work' for field 'complex_field'.*Unsupported coercion for type.*NonStringConstructible.* from value 'wont_work': invalid literal for int\(\) with base 10: 'wont_work'",
    ):
        await request_fail.form(model=WillFailModel)


@dataclass
class ListWithOptionalIntModel:
    items: list[int | None]


@pytest.mark.asyncio
async def test_form_coercion_list_with_optional_int_empty_item():
    request = await create_request_with_form_data({"items": ["1", "", "3"]})
    model_instance = await request.form(model=ListWithOptionalIntModel)
    assert model_instance.items == [1, None, 3]


@dataclass
class ListWithNonOptionalIntModel:
    items: list[int]


@pytest.mark.asyncio
async def test_form_coercion_list_with_non_optional_int_empty_item_fails():
    request = await create_request_with_form_data({"items": ["1", "", "3"]})
    with pytest.raises(
        ValueError,
        match=r"Error coercing item '' for field 'items'.*invalid literal for int\(\) with base 10: ''",
    ):
        await request.form(model=ListWithNonOptionalIntModel)


@dataclass
class UntypedListModel:
    stuff: list


@pytest.mark.asyncio
async def test_form_coercion_untyped_list_defaults_to_str():
    request = await create_request_with_form_data({"stuff": ["text", "123"]})
    model_instance = await request.form(model=UntypedListModel)
    assert model_instance.stuff == ["text", "123"]


@dataclass
class ListAnyModel:
    items: list[Any]


@pytest.mark.asyncio
async def test_form_coercion_list_any_type():
    form_values = {"items": ["text", "123", "True", "0.5"]}
    request = await create_request_with_form_data(form_values)
    model_instance = await request.form(model=ListAnyModel)
    # For List[Any], items should remain strings as received from the form
    assert model_instance.items == ["text", "123", "True", "0.5"]


@dataclass
class AnyFieldModel:
    field_a: Any
    field_b: Any | None = None


@pytest.mark.asyncio
async def test_form_coercion_any_field_type():
    form_values = {"field_a": "any_string_value", "field_b": "12345"}
    request = await create_request_with_form_data(form_values)
    model_instance = await request.form(model=AnyFieldModel)
    assert model_instance.field_a == "any_string_value"
    assert model_instance.field_b == "12345"


@pytest.mark.asyncio
async def test_form_coercion_any_field_type_empty_optional():
    form_values = {"field_a": "another", "field_b": ""}
    request = await create_request_with_form_data(form_values)
    model_instance = await request.form(model=AnyFieldModel)
    assert model_instance.field_a == "another"
    # Optional[Any] with empty string should become None due to _coerce_value Union logic first
    assert model_instance.field_b is None


@pytest.mark.asyncio
async def test_form_coercion_any_field_type_missing_optional():
    form_values = {"field_a": "last_one"}
    request = await create_request_with_form_data(form_values)
    model_instance = await request.form(model=AnyFieldModel)
    assert model_instance.field_a == "last_one"
    assert model_instance.field_b is None
