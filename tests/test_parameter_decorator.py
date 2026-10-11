from textwrap import dedent
from typing import Annotated

import pytest
from salix import Struct

from cyclopts import Parameter
from cyclopts.exceptions import UnknownOptionError


def test_parameter_decorator_struct(app, assert_parse_args):
    @Parameter(name="*")  # Flatten namespace.
    class User(Struct):
        name: str
        age: int

    @app.command
    def create(*, user: User | None = None):
        pass

    assert_parse_args(create, "create")
    assert_parse_args(create, "create --name=Bob --age=100", user=User("Bob", 100))  # pyright: ignore[reportCallIssue]


def test_parameter_decorator_struct_nested_1(app, console):
    """
    https://github.com/BrianPugh/cyclopts/issues/320
    """

    class S3Path(Struct):
        bucket: Annotated[str, Parameter()]
        key: Annotated[str, Parameter()]

    @Parameter(name="*")  # Flatten namespace.
    class S3CliParams(Struct):
        path: Annotated[S3Path, Parameter(name="*")]
        region: Annotated[str, Parameter(name="region")]

    @app.command
    def action(*, s3_path: S3CliParams):
        pass

    with console.capture() as capture:
        app("action --help", console=console)

    actual = capture.get()
    expected = dedent(
        """\
        Usage: test_parameter_decorator action --bucket STR --key STR --region
        STR

        ╭─ Parameters ───────────────────────────────────────────────────────╮
        │ *  --bucket  [required]                                            │
        │ *  --key     [required]                                            │
        │ *  --region  [required]                                            │
        ╰────────────────────────────────────────────────────────────────────╯
        """
    )
    assert actual == expected


def test_parameter_decorator_struct_inheritance(app, assert_parse_args):
    @Parameter(name="person")  # Should override the name="u" below.
    @Parameter(name="u", negative_bool=[])
    class User(Struct):
        name: str
        age: int
        privileged: bool = False

    @Parameter(name="a", negative_bool=None)  # Should revert to Cyclopts defaults
    class Admin(User):
        privileged: bool = True

    @app.command
    def create(*, user: User | None = None, admin: Admin | None = None):
        pass

    assert_parse_args(create, "create --person.name=Bob --person.age=100", user=User("Bob", 100))
    with pytest.raises(UnknownOptionError):
        app("create --person.no-privileged", exit_on_error=False)

    assert_parse_args(create, "create --a.name=Bob --a.age=100", admin=Admin("Bob", 100))
    assert_parse_args(
        create, "create --a.name=Bob --a.age=100 --a.no-privileged", admin=Admin("Bob", 100, privileged=False)
    )


def test_parameter_class_decorator_with_annotated(app, assert_parse_args):
    """Test that @Parameter on a class works when the type is wrapped in Annotated.

    This is a regression test for a bug where __cyclopts__ was checked before
    unwrapping Annotated, so class-level Parameter settings were ignored.
    """

    @Parameter(allow_leading_hyphen=True)
    class MyType:
        def __init__(self, value: str):
            self.value = value

        def __eq__(self, other):
            return self.value == other.value

    @app.default
    def foo(arg: Annotated[MyType, Parameter(help="Custom help text.")]):
        pass

    # The class-level allow_leading_hyphen=True should be respected
    # even when MyType is wrapped in Annotated with additional Parameter config
    assert_parse_args(foo, "-", arg=MyType("-"))
    assert_parse_args(foo, "--foo", arg=MyType("--foo"))


def test_parameter_class_decorator_with_annotated_optional_and_default(app, assert_parse_args):
    """Test that @Parameter on a class works with Annotated[Type | None, Parameter(...)] = None.

    Regression test for https://github.com/BrianPugh/cyclopts/issues/740

    The bug: When a type hint is Annotated[Type | None, Parameter(...)], the get_parameters
    function would:
    1. Call resolve_optional() on the Annotated type (which does nothing because Annotated is not a Union)
    2. Unwrap Annotated to get Type | None
    3. Try to get __cyclopts__ from Type | None (a Union), which fails

    The __cyclopts__ attribute from Type's @Parameter decorator was never extracted,
    so settings like allow_leading_hyphen=True were lost.
    """

    @Parameter(allow_leading_hyphen=True)
    class MyType:
        def __init__(self, value: str):
            self.value = value

        def __eq__(self, other):
            return self.value == other.value

    @app.default
    def foo(
        required_arg: MyType,
        optional_arg: Annotated[MyType | None, Parameter(name=["--opt", "-o"])] = None,
    ):
        pass

    # The class-level allow_leading_hyphen=True should be respected
    # even when MyType is wrapped in Annotated[... | None, ...] with a default
    assert_parse_args(foo, ["-", "-"], MyType("-"), MyType("-"))
    assert_parse_args(foo, ["-", "--opt", "-"], MyType("-"), MyType("-"))
    assert_parse_args(foo, ["-", "-o", "-"], MyType("-"), MyType("-"))
