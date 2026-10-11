import json
from typing import Annotated

import pytest
from salix import Struct

from cyclopts import CycloptsError, Parameter


class User(Struct):
    id: int
    name: str = "John Doe"
    tastes: dict[str, int] = {}


def test_bind_struct_from_env_json(app, assert_parse_args, monkeypatch):
    @app.command
    def foo(some_number: int, user: Annotated[User, Parameter(env_var="USER")]):
        pass

    external_data = {
        "id": 123,
        # "name" is purposely missing.
        "tastes": {
            "wine": 9,
            "cheese": 7,
            "cabbage": 1,
        },
    }
    monkeypatch.setenv("USER", json.dumps(external_data))
    assert_parse_args(
        foo,
        "foo 100",
        100,
        User(**external_data),
    )


@pytest.mark.parametrize(
    "cmd_str",
    [
        """--origin='{"x": 1, "y": 2}'""",
        """--origin '{"x": 1, "y": 2}'""",
        """--origin='{"x": 1, "y": 2, "label": null}'""",
    ],
)
def test_bind_struct_from_cli_json(app, assert_parse_args, cmd_str):
    class Coordinate(Struct):
        x: int
        y: int
        label: str | None = None

    @app.default
    def main(origin: Coordinate):
        pass

    assert_parse_args(main, cmd_str, Coordinate(1, 2))


def test_bind_struct_from_cli_json_empty(app, assert_parse_args):
    """An explicit empty JSON dict instantiates the struct from its defaults."""

    class Coordinate(Struct):
        x: int = 0
        y: int = 0

    @app.default
    def main(origin: Coordinate):
        pass

    assert_parse_args(main, "--origin={}", Coordinate())


def test_nested_struct_from_env_json(app, assert_parse_args, monkeypatch):
    """Test parsing nested structs from environment variable JSON."""

    class Address(Struct):
        street: str
        city: str
        zipcode: str | None = None

    class Person(Struct):
        name: str
        age: int
        address: Address
        hobbies: list[str] = []

    @app.default
    def main(person: Annotated[Person, Parameter(env_var="PERSON")]):
        pass

    person_data = {
        "name": "John Doe",
        "age": 30,
        "address": {"street": "123 Main St", "city": "Springfield", "zipcode": "12345"},
        "hobbies": ["reading", "gaming", "cooking"],
    }
    monkeypatch.setenv("PERSON", json.dumps(person_data))

    expected = Person(
        name="John Doe",
        age=30,
        address=Address(street="123 Main St", city="Springfield", zipcode="12345"),
        hobbies=["reading", "gaming", "cooking"],
    )
    assert_parse_args(main, "", expected)


def test_list_of_simple_struct_from_env(app, assert_parse_args, monkeypatch):
    """Test parsing list of simple structs from environment variable."""

    class Product(Struct):
        name: str
        price: float
        in_stock: bool = True

    @app.default
    def main(products: Annotated[list[Product], Parameter(env_var="PRODUCTS")]):
        pass

    products_data = [
        {"name": "Widget", "price": 19.99, "in_stock": True},
        {"name": "Gadget", "price": 29.99, "in_stock": False},
        {"name": "Doohickey", "price": 39.99},
    ]
    monkeypatch.setenv("PRODUCTS", json.dumps(products_data))

    expected = [
        Product(name="Widget", price=19.99, in_stock=True),
        Product(name="Gadget", price=29.99, in_stock=False),
        Product(name="Doohickey", price=39.99, in_stock=True),
    ]
    assert_parse_args(main, "", expected)


def test_complex_nested_type_validation_env_var(app, monkeypatch):
    """Test that type validation works for complex nested structures from env vars."""

    class Config(Struct):
        name: str
        value: int
        enabled: bool = True

    @app.default
    def main(config: Annotated[Config, Parameter(env_var="CONFIG")]):
        pass

    # Invalid type for 'value' field - should be int but providing string
    invalid_data = {"name": "test", "value": "not_an_int", "enabled": True}
    monkeypatch.setenv("CONFIG", json.dumps(invalid_data))

    with pytest.raises(CycloptsError):
        app([], exit_on_error=False)
