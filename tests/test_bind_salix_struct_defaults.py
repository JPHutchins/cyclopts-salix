from textwrap import dedent
from typing import Annotated

import pytest
import salix

from cyclopts import Parameter
from cyclopts.exceptions import UnknownOptionError


class Outfit(salix.Struct):
    body: str
    head: str


class User(salix.Struct):
    id: int
    name: str = "John Doe"
    tastes: dict[str, int] = {}
    outfit: Outfit | None = None
    admin: Annotated[bool, Parameter(negative="not-admin")] = False
    vip: Annotated[bool, Parameter(negative="--not-vip")] = False
    staff: Annotated[bool, Parameter(parse=False)] = False


def test_bind_salix_struct(app, assert_parse_args, console):
    @app.command
    def foo(user: User):
        pass

    assert_parse_args(
        foo,
        "foo --user.id=123 --user.tastes.wine=9 --user.tastes.cheese=7 --user.tastes.cabbage=1 --user.outfit.body=t-shirt --user.outfit.head=baseball-cap --user.admin",
        User(
            id=123,
            tastes={"wine": 9, "cheese": 7, "cabbage": 1},
            outfit=Outfit(body="t-shirt", head="baseball-cap"),
            admin=True,
        ),
    )

    with console.capture() as capture:
        app("foo --help", console=console)

    actual = capture.get()

    expected = dedent(
        """\
        Usage: test_bind_salix_struct_defaults foo USER.ID [ARGS]

        ╭─ Parameters ───────────────────────────────────────────────────────╮
        │ *  USER.ID --user.id      [required]                               │
        │    USER.NAME --user.name  [default: John Doe]                      │
        │    --user.tastes          [default: {}]                            │
        │    --user.outfit.body                                              │
        │    --user.outfit.head                                              │
        │    --user.admin           [default: False]                         │
        │      --user.not-admin                                              │
        │    --user.vip --not-vip   [default: False]                         │
        ╰────────────────────────────────────────────────────────────────────╯
        """
    )
    assert actual == expected


def test_bind_salix_struct_flatten(app, assert_parse_args, console):
    @app.command
    def foo(user: Annotated[User, Parameter(name="*")]):
        pass

    assert_parse_args(
        foo,
        "foo --id=123 --tastes.wine=9 --tastes.cheese=7 --tastes.cabbage=1 --outfit.body=t-shirt --outfit.head=baseball-cap --admin",
        User(
            id=123,
            tastes={"wine": 9, "cheese": 7, "cabbage": 1},
            outfit=Outfit(body="t-shirt", head="baseball-cap"),
            admin=True,
        ),
    )

    with console.capture() as capture:
        app("foo --help", console=console)

    actual = capture.get()

    expected = dedent(
        """\
        Usage: test_bind_salix_struct_defaults foo ID [ARGS]

        ╭─ Parameters ───────────────────────────────────────────────────────╮
        │ *  ID --id              [required]                                 │
        │    NAME --name          [default: John Doe]                        │
        │    --tastes             [default: {}]                              │
        │    --outfit.body                                                   │
        │    --outfit.head                                                   │
        │    --admin --not-admin  [default: False]                           │
        │    --vip --not-vip      [default: False]                           │
        ╰────────────────────────────────────────────────────────────────────╯
        """
    )
    assert actual == expected


def test_bind_salix_struct_accepts_keys_false(app, assert_parse_args, console):
    class SimpleClass(salix.Struct):
        value: int
        name: str

    @app.command
    def foo(example: Annotated[SimpleClass, Parameter(accepts_keys=False)]):
        pass

    assert_parse_args(foo, "foo 5 foo", SimpleClass(5, "foo"))
    assert_parse_args(foo, "foo --example=5 foo", SimpleClass(5, "foo"))

    with console.capture() as capture:
        app("foo --help", console=console)

    actual = capture.get()

    expected = dedent(
        """\
        Usage: test_bind_salix_struct_defaults foo EXAMPLE

        ╭─ Parameters ───────────────────────────────────────────────────────╮
        │ *  EXAMPLE --example  [required]                                   │
        ╰────────────────────────────────────────────────────────────────────╯
        """
    )
    assert actual == expected



def test_bind_salix_struct_unknown_option(app, assert_parse_args):
    class Engine(salix.Struct):
        cylinders: int
        volume: float

    @app.default
    def default(engine: Engine):
        pass

    with pytest.raises(UnknownOptionError):
        app("--engine.cylinders 4 --this-parameter-does-not-exist 100", exit_on_error=False)




def test_salix_struct_inheritance_simple(app, console):
    """Test that docstrings from base struct class are inherited by derived class."""

    class BaseClass(salix.Struct):
        """Base class."""

        some_arg: int = 42
        """BaseClass.some_arg docstring."""

    class DerivedClass(BaseClass):
        """Derived class."""

        some_other_arg: str = "some_other_arg default value"
        """DerivedClass.some_other_arg docstring."""

    @app.default
    def main(params: DerivedClass):
        pass

    with console.capture() as capture:
        app("--help", console=console)

    actual = capture.get()

    # Check that both base and derived docstrings are present
    assert "BaseClass.some_arg docstring." in actual
    assert "DerivedClass.some_other_arg docstring." in actual


def test_bind_salix_struct_command_factory_help(app, console):
    """Struct commands must not leak a sentinel into help text.

    https://github.com/BrianPugh/cyclopts/issues/857
    """

    @app.command
    class Test(salix.Struct):
        numbers: list[int] = [1, 2, 3]

    with console.capture() as capture:
        app("test --help", console=console)

    actual = capture.get()

    assert "NOTHING" not in actual
    assert "[default: [1, 2, 3]]" in actual
