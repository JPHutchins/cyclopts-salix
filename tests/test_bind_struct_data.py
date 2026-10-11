from textwrap import dedent
from typing import Annotated

import pytest
import salix

import cyclopts
from cyclopts import Parameter
from cyclopts.exceptions import MissingArgumentError


class User(salix.Struct):
    id: int
    name: str = "John Doe"
    tastes: dict[str, int] = {}


def test_bind_salix_struct(app, assert_parse_args, console):
    @app.command
    def foo(some_number: int, user: User):
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
    assert_parse_args(
        foo,
        "foo 100 --user.id=123 --user.tastes.wine=9 --user.tastes.cheese=7 --user.tastes.cabbage=1",
        100,
        User(**external_data),
    )


def test_bind_salix_struct_missing_all_arguments(app, assert_parse_args, console):
    """We expect to see the first subargument (--user.id) in the error message,
    not the root "--user".
    """

    @app.default
    def default(some_number: int, user: User):
        pass

    with console.capture() as capture, pytest.raises(MissingArgumentError):
        app("123", error_console=console, exit_on_error=False)
    actual = capture.get()

    expected = dedent(
        """\
        ╭─ Error ────────────────────────────────────────────────────────────╮
        │ Parameter --user.id requires an argument.                          │
        ╰────────────────────────────────────────────────────────────────────╯
        """
    )

    assert actual == expected


def test_bind_salix_struct_recursive(app, assert_parse_args, console, normalize_trailing_whitespace):
    class Wheel(salix.Struct):
        diameter: int
        "Diameter of wheel in inches."

    class Engine(salix.Struct):
        cylinders: int
        "Number of cylinders the engine has."

        hp: Annotated[float, Parameter(name=("horsepower", "p"))]
        "Amount of horsepower the engine can generate."

        diesel: bool = False
        "If this engine consumes diesel, instead of gasoline."

    class Car(salix.Struct):
        name: str
        "The name/model of the car."

        mileage: float
        "How many miles the car has driven."

        engine: Annotated[Engine, Parameter(name="*", group="Engine")]
        "The kind of engine the car is using."

        wheel: Wheel
        "The kind of wheels the car is using."

        n_axles: int = 2
        "Number of axles the car has."

    @app.command
    def build(*, license_plate: str, car: Car):
        """Build a car.

        Parameters
        ----------
        license_plate: str
            License plate identifier to give to car.
        car: Car
            Car specifications.
        """

    assert_parse_args(
        build,
        "build --car.name=ford --car.mileage=500 --car.cylinders=4 --car.p=200 --car.wheel.diameter=18 --license-plate=ABCDEFG",
        car=Car(
            name="ford",
            mileage=500,
            engine=Engine(cylinders=4, hp=200),
            wheel=Wheel(diameter=18),
        ),
        license_plate="ABCDEFG",
    )

    with console.capture() as capture:
        app("build --help", console=console)

    actual = capture.get()

    expected = dedent(
        """\
        Usage: test_bind_struct_data build --license-plate STR --car.name STR
        --car.mileage FLOAT --car.cylinders INT --car.horsepower FLOAT
        --car.wheel.diameter INT [OPTIONS]

        Build a car.

        ╭─ Parameters ───────────────────────────────────────────────────────╮
        │ *  --license-plate       License plate identifier to give to car.  │
        │                          [required]                                │
        │ *  --car.name            The name/model of the car. [required]     │
        │ *  --car.mileage         How many miles the car has driven.        │
        │                          [required]                                │
        │ *  --car.wheel.diameter  Diameter of wheel in inches. [required]   │
        │    --car.n-axles         Number of axles the car has. [default: 2] │
        ╰────────────────────────────────────────────────────────────────────╯
        ╭─ Engine ───────────────────────────────────────────────────────────╮
        │ *  --car.cylinders           Number of cylinders the engine has.   │
        │                              [required]                            │
        │ *  --car.horsepower --car.p  Amount of horsepower the engine can   │
        │                              generate. [required]                  │
        │    --car.diesel              If this engine consumes diesel,       │
        │      --car.no-diesel         instead of gasoline. [default: False] │
        ╰────────────────────────────────────────────────────────────────────╯
        """
    )

    assert normalize_trailing_whitespace(actual) == expected


def test_bind_salix_struct_recursive_missing_arg(app, assert_parse_args, console):
    """The ``engine`` parameter itself is optional, but if specified it has 2 required fields."""

    class Engine(salix.Struct):
        cylinders: int
        hp: float = 100

    class Car(salix.Struct):
        name: str
        mileage: float
        engine: Annotated[Engine, Parameter(name="*", group="Engine")] = Engine(8, 500)

    @app.command
    def build(*, license_plate: str, car: Car):
        pass

    # Specifying a complete engine works.
    assert_parse_args(
        build,
        "build --car.name=ford --car.mileage=500 --car.cylinders=4 --car.hp=200 --license-plate=ABCDEFG",
        car=Car(name="ford", mileage=500, engine=Engine(cylinders=4, hp=200)),
        license_plate="ABCDEFG",
    )

    # Specifying NO engine works.
    assert_parse_args(
        build,
        "build --car.name=ford --car.mileage=500 --license-plate=ABCDEFG",
        car=Car(name="ford", mileage=500),
        license_plate="ABCDEFG",
    )

    # Partially defining an engine does NOT work.
    with console.capture() as capture, pytest.raises(MissingArgumentError):
        app.parse_args(
            "build --car.name=ford --car.mileage=500 --car.hp=200 --license-plate=ABCDEFG",
            error_console=console,
            exit_on_error=False,
        )

    actual = capture.get()

    expected = dedent(
        """\
        ╭─ Error ────────────────────────────────────────────────────────────╮
        │ Command "build" parameter --car.cylinders requires an argument.    │
        ╰────────────────────────────────────────────────────────────────────╯
        """
    )

    assert actual == expected


@pytest.mark.parametrize(
    "cmd",
    [
        "'Bob Smith' 30",
        "--nickname='Bob Smith' --player.years-young=30",
    ],
)
def test_bind_salix_struct_double_name_override_no_hyphen(app, assert_parse_args, console, cmd):
    class User(salix.Struct):
        # Beginning with "--" will completely override the parenting parameter name.
        name: Annotated[str, Parameter(name="--nickname")]
        # Not beginning with "--" will tack it on to the parenting parameter name.
        age: Annotated[int, Parameter(name="years-young")]

    @app.default
    def main(user: Annotated[User, Parameter(name="player")]):  # but what about without --?
        print(user)

    assert_parse_args(main, cmd, user=User("Bob Smith", 30))


@pytest.mark.parametrize(
    "cmd_str",
    [
        "100 200",
        "--a 100 --bar 200",
        "--bar 200 100",
    ],
)
def test_bind_salix_struct_positionally(app, assert_parse_args, cmd_str, console):
    class Config(salix.Struct):
        a: int
        """Docstring for a."""

        b: Annotated[int, Parameter(name="bar")] = 2
        """This is the docstring for python parameter "b"."""

    @app.default
    def my_default_command(config: Annotated[Config, Parameter(name="*")]):
        print(f"{config=}")

    assert_parse_args(my_default_command, cmd_str, Config(a=100, b=200))

    with console.capture() as capture:
        app("build --help", console=console)

    actual = capture.get()
    expected = dedent(
        """\
        Usage: test_bind_struct_data A [ARGS]

        ╭─ Commands ─────────────────────────────────────────────────────────╮
        │ --help (-h)  Display this message and exit.                        │
        │ --version    Display application version.                          │
        ╰────────────────────────────────────────────────────────────────────╯
        ╭─ Parameters ───────────────────────────────────────────────────────╮
        │ *  A --a      Docstring for a. [required]                          │
        │    BAR --bar  This is the docstring for python parameter "b".      │
        │               [default: 2]                                         │
        ╰────────────────────────────────────────────────────────────────────╯
        """
    )
    assert actual == expected


def test_bind_salix_struct_list_default_help(app, console):
    class Config(salix.Struct):
        a: int = 5
        """Docstring for a."""

    @app.default
    def my_default_command(config: Annotated[Config | None, Parameter(name="*")] = None):
        print(f"{config=}")

    with console.capture() as capture:
        app("--help", console=console)

    actual = capture.get()
    expected = dedent(
        """\
        Usage: test_bind_struct_data [ARGS]

        ╭─ Commands ─────────────────────────────────────────────────────────╮
        │ --help (-h)  Display this message and exit.                        │
        │ --version    Display application version.                          │
        ╰────────────────────────────────────────────────────────────────────╯
        ╭─ Parameters ───────────────────────────────────────────────────────╮
        │ A --a  Docstring for a. [default: 5]                               │
        ╰────────────────────────────────────────────────────────────────────╯
        """
    )
    assert actual == expected








def test_bind_salix_struct_tuple_in_var_args(app, assert_parse_args):
    class Square(salix.Struct):
        center: tuple[float, float]
        side_length: float

    @app.default
    def my_default_command(*squares: Square):
        pass

    assert_parse_args(my_default_command, "10 20 30", Square(center=(10.0, 20.0), side_length=30.0))


def test_bind_salix_struct_with_alias_attribute(app, assert_parse_args):
    """https://github.com/BrianPugh/cyclopts/issues/505"""

    @Parameter(name="*", negative=False)
    class StructParameters(salix.Struct):
        with_alias: Annotated[
            bool,
            Parameter(
                alias="-a",
                help="Parameter that uses alias.",
            ),
        ] = False

        with_iterable: Annotated[
            bool, Parameter(["--with-iterable", "-i"], help="Parameter that uses an iterable as name.")
        ] = False

    @app.default
    def main(*, params: StructParameters | None = None) -> None:
        pass

    assert_parse_args(main, "-a", params=StructParameters(with_alias=True, with_iterable=False))
    assert_parse_args(main, "--with-alias", params=StructParameters(with_alias=True, with_iterable=False))


def test_bind_salix_struct_star_parameter_better_error_message(app, console):
    """Test that Parameter(name="*") raises ValueError at app setup time when parameter has no default."""

    @Parameter(name="*")
    class Foo(salix.Struct):
        bar: int = 12

    def cmd(foo: Foo):
        print(foo)

    expected_message = (
        r'Parameter "foo" in function .* has all optional values, uses Parameter\(name="\*"\), but itself has no default value\. Consider either:\n'
        r'    1\) If immutable, providing a default value "foo: Foo = Foo\(\)"\n'
        r'    2\) Otherwise, declaring it optional like "foo: Foo \| None = None" and instanting the foo object in the function body:\n'
        r"           if foo is None:\n"
        r"               foo = Foo\(\)"
    )

    with pytest.raises(ValueError, match=expected_message):
        app.default(cmd)


def test_bind_salix_struct_with_varargs_consume_all(app, assert_parse_args):
    """Test struct with *args field that consumes all remaining tokens."""

    class FileProcessor(salix.Struct):
        output: str
        inputs: tuple[str, ...]

    @app.default
    def process(config: Annotated[FileProcessor, Parameter(name="*")]):
        pass

    assert_parse_args(
        process,
        "out.txt in1.txt in2.txt in3.txt",
        config=FileProcessor(output="out.txt", inputs=("in1.txt", "in2.txt", "in3.txt")),
    )





def test_bind_salix_struct_direct_parent_match_issue_647(app, assert_parse_args):
    """Test that --foo bar baz correctly converts to Foo(name="bar", age=25).

    Previously, parent arguments with children would match directly (e.g., --foo),
    consume tokens, but then fail to properly construct the object because
    children had no tokens. The fix allows parent arguments to convert their
    tokens as positional arguments to the structured type.

    See: https://github.com/BrianPugh/cyclopts/issues/647
    """

    class Foo(salix.Struct):
        name: str
        age: int

    @app.default
    def cmd(*, foo: Annotated[Foo, Parameter()] = Foo(name="default", age=0)):  # noqa: B008
        return foo

    # This should work: directly provide values after parent name (positional-style)
    assert_parse_args(cmd, "--foo bar 25", foo=Foo(name="bar", age=25))

    # This should also still work: explicit nested keys
    assert_parse_args(cmd, "--foo.name baz --foo.age 30", foo=Foo(name="baz", age=30))

    # No arguments should use the function default (tested separately)
    _, bound, _ = app.parse_args("", print_error=False, exit_on_error=False)
    assert "foo" not in bound.arguments
    result = cmd(**bound.arguments)
    assert result == Foo(name="default", age=0)








def test_salix_struct_inheritance_simple(app, console):
    """Test that docstrings from base struct are inherited by derived class.

    Regression test for: https://github.com/BrianPugh/cyclopts/issues/691
    """

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


def test_salix_struct_inheritance_multi_level(app, console):
    """Test that docstrings propagate through multiple inheritance levels."""

    class GrandparentClass(salix.Struct):
        """Grandparent class."""

        grandparent_field: int = 1
        """Grandparent field doc."""

    class ParentClass(GrandparentClass):
        """Parent class."""

        parent_field: int = 2
        """Parent field doc."""

    class ChildClass(ParentClass):
        """Child class."""

        child_field: int = 3
        """Child field doc."""

    @app.default
    def main(params: ChildClass):
        pass

    with console.capture() as capture:
        app("--help", console=console)

    actual = capture.get()

    # Check that all three levels of docstrings are present
    assert "Grandparent field doc." in actual
    assert "Parent field doc." in actual
    assert "Child field doc." in actual


def test_salix_struct_inheritance_override_docstring(app, console):
    """Test that derived class can override base class docstrings."""

    class BaseClass(salix.Struct):
        """Base class."""

        shared_field: int = 1
        """Base docstring."""

    class DerivedClass(BaseClass):
        """Derived class."""

        shared_field: int = 2
        """Derived docstring overrides base."""

        new_field: str = "new"
        """New field in derived."""

    @app.default
    def main(params: DerivedClass):
        pass

    with console.capture() as capture:
        app("--help", console=console)

    actual = capture.get()

    # Derived class docstring should take precedence
    assert "Derived docstring overrides base." in actual
    assert "Base docstring." not in actual
    assert "New field in derived." in actual


def test_salix_struct_inheritance_with_parameter_name_star(app, console, normalize_trailing_whitespace):
    """Test inheritance with Parameter(name='*') works correctly."""

    class BaseConfig(salix.Struct):
        """Base configuration."""

        verbose: bool = False
        """Enable verbose output."""

    class ExtendedConfig(BaseConfig):
        """Extended configuration."""

        debug: bool = False
        """Enable debug mode."""

    @app.default
    def main(config: Annotated[ExtendedConfig | None, Parameter(name="*")] = None):
        pass

    with console.capture() as capture:
        app("--help", console=console)

    actual = capture.get()

    # Both base and derived docstrings should be present
    assert "Enable verbose output." in actual
    assert "Enable debug mode." in actual


def test_salix_struct_inheritance_no_docstrings_in_derived(app, console):
    """Test that base docstrings work even if derived class has no docstrings."""

    class BaseClass(salix.Struct):
        """Base class."""

        base_field: int = 1
        """Base field documentation."""

    class DerivedClass(BaseClass):
        """Derived class."""

        # No docstring for this field
        derived_field: int = 2

    @app.default
    def main(params: DerivedClass):
        pass

    with console.capture() as capture:
        app("--help", console=console)

    actual = capture.get()

    # Base docstring should be present
    assert "Base field documentation." in actual


def test_bind_salix_struct_with_parameter_alias_issue_696(app, assert_parse_args, console):
    """Test that user class with parameter alias generates correct arguments.

    https://github.com/BrianPugh/cyclopts/issues/696

    When using a user class as a parameter with an alias, the generated
    arguments should use the class attribute names, not the parameter alias.

    For example, parameter `source` with alias `from`, and class attribute `server`:
    - Should generate: --source.server, --from.server
    - Should NOT generate: --source.from, --from.from
    """

    class Source(salix.Struct):
        server: str
        port: int = 8080

    @app.default
    def main(source: Annotated[Source, Parameter(name="source", alias="from")]):
        return source

    # Check the help output to see what arguments are generated
    with console.capture() as capture:
        app("--help", console=console)

    actual = capture.get()

    # Should have the correct arguments
    assert "--source.server" in actual, "Missing --source.server"
    assert "--from.server" in actual, "Missing --from.server"

    # Should NOT have the incorrect arguments (using parameter alias as attribute name)
    assert "--source.from" not in actual, "Incorrectly generated --source.from"
    assert "--from.from" not in actual, "Incorrectly generated --from.from"

    # Test with --source.server (should work)
    assert_parse_args(
        main,
        "--source.server=localhost --source.port=9000",
        source=Source(server="localhost", port=9000),
    )

    # Test with --from.server (should work)
    assert_parse_args(
        main,
        "--from.server=localhost --from.port=9000",
        source=Source(server="localhost", port=9000),
    )

    # Test mixed usage (should work)
    assert_parse_args(
        main,
        "--source.server=localhost --from.port=9000",
        source=Source(server="localhost", port=9000),
    )


def test_bind_salix_struct_default_parameter_consume_multiple_propagates(assert_parse_args):
    """``default_parameter`` settings should propagate to inner struct fields.

    Previously ``name_transform`` propagated correctly, but ``consume_multiple`` did
    not unless the inner class field was explicitly annotated.

    https://github.com/BrianPugh/cyclopts/issues/841
    """
    app = cyclopts.App(
        result_action="return_value",
        default_parameter=Parameter(consume_multiple=True),
    )

    class Inner(salix.Struct):
        names: list[str]

    @app.command
    def cmd(office: str, /, *, inner: Inner):
        pass

    actual_command, actual_bind, _ = app.parse_args(
        "cmd my_office --inner.names name1 name2",
        print_error=False,
        exit_on_error=False,
    )
    assert actual_command == cmd
    assert actual_bind.args == ("my_office",)
    assert actual_bind.kwargs == {"inner": Inner(names=["name1", "name2"])}


def test_bind_salix_struct_accepts_keys_list_default(app, assert_parse_args):
    """Explicit ``accepts_keys=True`` on a struct with a list default field.

    https://github.com/BrianPugh/cyclopts/issues/857
    """

    class Config(salix.Struct):
        numbers: list[int] = [1, 2, 3]

    @app.command
    def cmd(config: Annotated[Config | None, Parameter(accepts_keys=True)] = None):
        pass

    assert_parse_args(cmd, "cmd")
    assert_parse_args(cmd, "cmd --config.numbers=5", Config(numbers=[5]))
