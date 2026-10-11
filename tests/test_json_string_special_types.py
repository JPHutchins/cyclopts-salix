"""Test JSON parsing behavior with special string types.

This module tests JSON parsing with:
- String subclasses (CustomStr)
- NewType wrapping str
- Union types containing str
- Optional[str] (which is Union[str, None])

Key principle: If a type can accept str, then a JSON string is already
a valid value for that type, so JSON parsing should be disabled.
"""

from typing import Annotated, NewType

import pytest
from salix import Struct

from cyclopts import Parameter


class CustomStr(str):
    """A custom string subclass."""


MyStr = NewType("MyStr", str)


class User(Struct):
    name: str
    age: int


class UserWithCustomStr(Struct):
    name: CustomStr
    age: int


class UserWithNewType(Struct):
    name: MyStr
    age: int


class UserWithUnion(Struct):
    name: str | int
    age: int


# =============================================================================
# Tests for string subclasses and NewType
# =============================================================================


@pytest.mark.parametrize(
    "type_hint,expected_value",
    [
        (CustomStr, CustomStr('{"name": "Alice"}')),
        (MyStr, MyStr('{"name": "Alice"}')),
    ],
    ids=["CustomStr", "NewType"],
)
def test_json_not_parsed_for_str_like_types(app, assert_parse_args, type_hint, expected_value):
    """JSON should NOT be parsed for string subclasses or NewType(str)."""

    @app.default
    def main(value: type_hint):  # type: ignore
        pass

    assert_parse_args(
        main,
        ["--value", '{"name": "Alice"}'],
        expected_value,
    )


@pytest.mark.parametrize(
    "type_hint,expected_value",
    [
        (CustomStr, CustomStr('{"name": "Alice"}')),
        (MyStr, MyStr('{"name": "Alice"}')),
    ],
    ids=["CustomStr", "NewType"],
)
def test_json_not_parsed_for_str_like_types_env_var(app, assert_parse_args, type_hint, expected_value, monkeypatch):
    """JSON should NOT be parsed for string subclasses or NewType(str) from environment variables."""
    monkeypatch.setenv("VALUE", '{"name": "Alice"}')

    @app.default
    def main(value: Annotated[type_hint, Parameter(env_var="VALUE")]):  # type: ignore
        pass

    assert_parse_args(main, "", expected_value)


@pytest.mark.parametrize(
    "type_hint,wrapper",
    [
        (list[CustomStr], CustomStr),
        (list[MyStr], MyStr),
    ],
    ids=["list[CustomStr]", "list[NewType]"],
)
def test_json_list_not_parsed_for_str_like_types(app, assert_parse_args, type_hint, wrapper):
    """JSON arrays should NOT be parsed for list of string-like types."""

    @app.default
    def main(values: type_hint):  # type: ignore
        pass

    assert_parse_args(
        main,
        ["--values", '["hello", "world"]'],
        [wrapper('["hello", "world"]')],
    )


# =============================================================================
# Tests for Union types containing str
# =============================================================================


@pytest.mark.parametrize(
    "type_hint,json_input,expected",
    [
        # Union[str, int] - JSON not parsed
        (list[str | int], "[1, 2, 3]", ["[1, 2, 3]"]),
        (list[str | int], '["hello", "world"]', ['["hello", "world"]']),
        # Optional[str] - JSON not parsed
        (list[str | None], '["hello", null, "world"]', ['["hello", null, "world"]']),
        # Optional[int] - JSON IS parsed (no str in union)
        (list[int | None], "[1, null, 3]", [1, None, 3]),
    ],
    ids=["Union[str,int]-ints", "Union[str,int]-strings", "Optional[str]", "Optional[int]"],
)
def test_json_list_parsing_with_unions(app, assert_parse_args, type_hint, json_input, expected):
    """Test JSON array parsing behavior with Union types.

    When Union contains str, JSON parsing is disabled since the JSON string
    is a valid str value.
    """

    @app.default
    def main(values: type_hint):  # type: ignore
        pass

    assert_parse_args(
        main,
        ["--values", json_input],
        expected,
    )


def test_union_with_str_no_json_parsing(app, assert_parse_args):
    """JSON should NOT be parsed when type is Union[str, ...]."""

    @app.default
    def main(value: str | int):
        pass

    assert_parse_args(
        main,
        ["--value", '{"name": "Alice"}'],
        '{"name": "Alice"}',
    )


def test_union_with_str_no_json_parsing_env_var(app, assert_parse_args, monkeypatch):
    """JSON should NOT be parsed from env var when type is Union[str, ...]."""
    json_str = '{"name": "Alice"}'
    monkeypatch.setenv("VALUE", json_str)

    @app.default
    def main(value: Annotated[str | int, Parameter(env_var="VALUE")]):
        pass

    assert_parse_args(main, "", json_str)


# =============================================================================
# Tests for structs with special string fields
# =============================================================================


@pytest.mark.parametrize(
    "struct_type,expected",
    [
        (UserWithCustomStr, UserWithCustomStr(CustomStr("Alice"), 30)),
        (UserWithNewType, UserWithNewType(MyStr("Alice"), 30)),
    ],
    ids=["CustomStr-field", "NewType-field"],
)
def test_json_struct_with_special_str_fields(app, assert_parse_args, struct_type, expected):
    """JSON object parsing works for structs with special string field types."""

    @app.default
    def main(user: struct_type):  # type: ignore
        pass

    assert_parse_args(
        main,
        ["--user", '{"name": "Alice", "age": 30}'],
        expected,
    )


def test_json_struct_with_union_field(app, assert_parse_args):
    """JSON object parsing works for structs with Union fields."""

    @app.default
    def main(user: UserWithUnion):
        pass

    # String value in union field
    assert_parse_args(
        main,
        ["--user", '{"name": "Alice", "age": 30}'],
        UserWithUnion("Alice", 30),
    )

    # Integer value in union field - gets converted to string since str is first in Union
    assert_parse_args(
        main,
        ["--user", '{"name": 123, "age": 30}'],
        UserWithUnion("123", 30),  # 123 becomes "123" due to Union coercion order
    )


@pytest.mark.parametrize(
    "struct_type,expected_type,name_wrapper",
    [
        (UserWithCustomStr, UserWithCustomStr, CustomStr),
        (UserWithNewType, UserWithNewType, MyStr),
    ],
    ids=["list[CustomStr-struct]", "list[NewType-struct]"],
)
def test_json_list_of_struct_with_special_fields(
    app, assert_parse_args, struct_type, expected_type, name_wrapper
):
    """JSON array parsing works for list of structs with special string fields."""

    @app.default
    def main(users: list[struct_type]):  # type: ignore
        pass

    assert_parse_args(
        main,
        ["--users", '[{"name": "Alice", "age": 30}, {"name": "Bob", "age": 40}]'],
        [expected_type(name_wrapper("Alice"), 30), expected_type(name_wrapper("Bob"), 40)],
    )


@pytest.mark.parametrize(
    "type_hint,cmd_args,expected",
    [
        # Regular struct - JSON IS parsed
        (
            list[User],
            ["--values", '{"name": "Alice", "age": 30}', "--values", '{"name": "Bob", "age": 40}'],
            [User("Alice", 30), User("Bob", 40)],
        ),
        # CustomStr - JSON NOT parsed
        (
            list[CustomStr],
            ["--values", '{"name": "Alice"}', "--values", '{"name": "Bob"}'],
            [CustomStr('{"name": "Alice"}'), CustomStr('{"name": "Bob"}')],
        ),
    ],
    ids=["list[Dataclass]-parses", "list[CustomStr]-no-parse"],
)
def test_multiple_json_objects(app, assert_parse_args, type_hint, cmd_args, expected):
    """Test multiple individual JSON objects for lists."""

    @app.default
    def main(values: type_hint):  # type: ignore
        pass

    assert_parse_args(main, cmd_args, expected)
