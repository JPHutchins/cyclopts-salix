"""Tests for structured types with various parameter kinds (POSITIONAL_ONLY, VAR_POSITIONAL, etc)."""

from typing import Annotated

from salix import Struct

from cyclopts import Parameter


class GenericClassWithMixedKinds:
    """A generic class that uses __init__ with mixed parameter kinds."""

    def __init__(self, pos_only: int, /, normal: str, *args: int, kw_only: float, **kwargs: str):
        self.pos_only = pos_only
        self.normal = normal
        self.args = args
        self.kw_only = kw_only
        self.kwargs = kwargs

    def __eq__(self, other):
        if not isinstance(other, GenericClassWithMixedKinds):
            return NotImplemented
        return (
            self.pos_only == other.pos_only
            and self.normal == other.normal
            and self.args == other.args
            and self.kw_only == other.kw_only
            and self.kwargs == other.kwargs
        )

    def __repr__(self):
        return (
            f"GenericClassWithMixedKinds(pos_only={self.pos_only}, normal={self.normal}, "
            f"args={self.args}, kw_only={self.kw_only}, kwargs={self.kwargs})"
        )


class GenericClassPositionalOnly:
    """A class with only positional-only parameters."""

    def __init__(self, a: int, b: str, /):
        self.a = a
        self.b = b

    def __eq__(self, other):
        if not isinstance(other, GenericClassPositionalOnly):
            return NotImplemented
        return self.a == other.a and self.b == other.b

    def __repr__(self):
        return f"GenericClassPositionalOnly(a={self.a}, b={self.b})"


class GenericClassKeywordOnly:
    """A class with only keyword-only parameters."""

    def __init__(self, *, x: int, y: str):
        self.x = x
        self.y = y

    def __eq__(self, other):
        if not isinstance(other, GenericClassKeywordOnly):
            return NotImplemented
        return self.x == other.x and self.y == other.y

    def __repr__(self):
        return f"GenericClassKeywordOnly(x={self.x}, y={self.y})"


class GenericClassPositionalOnlyAndKeywordOnly:
    """A class with both positional-only and keyword-only parameters."""

    def __init__(self, a: int, /, *, z: str):
        self.a = a
        self.z = z

    def __eq__(self, other):
        if not isinstance(other, GenericClassPositionalOnlyAndKeywordOnly):
            return NotImplemented
        return self.a == other.a and self.z == other.z

    def __repr__(self):
        return f"GenericClassPositionalOnlyAndKeywordOnly(a={self.a}, z={self.z})"


def test_generic_class_positional_only(app, assert_parse_args):
    """Test that POSITIONAL_ONLY parameters are passed as positional arguments."""

    @app.default
    def cmd(obj: Annotated[GenericClassPositionalOnly, Parameter(name="*")]):
        return obj

    assert_parse_args(cmd, "42 hello", obj=GenericClassPositionalOnly(42, "hello"))


def test_generic_class_keyword_only(app, assert_parse_args):
    """Test that KEYWORD_ONLY parameters are passed as keyword arguments."""

    @app.default
    def cmd(obj: Annotated[GenericClassKeywordOnly, Parameter(name="*")]):
        return obj

    # Should work with keywords
    assert_parse_args(cmd, "--x 10 --y world", obj=GenericClassKeywordOnly(x=10, y="world"))


def test_generic_class_keyword_only_positionally(app, assert_parse_args):
    """Test keyword-only class with accepts_keys=False (forces positional parsing)."""

    @app.default
    def cmd(obj: Annotated[GenericClassKeywordOnly, Parameter(name="obj", accepts_keys=False)]):
        return obj

    # With accepts_keys=False, values are passed positionally but converted to kwargs internally
    assert_parse_args(cmd, "--obj 10 world", obj=GenericClassKeywordOnly(x=10, y="world"))


def test_generic_class_positional_only_and_keyword_only(app, assert_parse_args):
    """Test mixed POSITIONAL_ONLY and KEYWORD_ONLY parameters."""

    @app.default
    def cmd(obj: Annotated[GenericClassPositionalOnlyAndKeywordOnly, Parameter(name="*")]):
        return obj

    # Positional-only passed as positional, keyword-only as keyword
    assert_parse_args(cmd, "5 --z test", obj=GenericClassPositionalOnlyAndKeywordOnly(5, z="test"))

    # This tests the critical fix: positional value for 'a', keyword arg for 'z'
    assert_parse_args(cmd, "--z test 5", obj=GenericClassPositionalOnlyAndKeywordOnly(5, z="test"))


def test_generic_class_all_keyword_or_positional(app, assert_parse_args):
    """Test that POSITIONAL_OR_KEYWORD works correctly."""

    class SimpleClass:
        def __init__(self, x: int, y: str):
            self.x = x
            self.y = y

        def __eq__(self, other):
            if not isinstance(other, SimpleClass):
                return NotImplemented
            return self.x == other.x and self.y == other.y

    @app.default
    def cmd(obj: Annotated[SimpleClass, Parameter(name="*")]):
        return obj

    # Both should work: positional and keyword
    assert_parse_args(cmd, "42 hello", obj=SimpleClass(42, "hello"))
    assert_parse_args(cmd, "--x 42 --y hello", obj=SimpleClass(42, "hello"))


class StructInner(Struct):
    name: str
    age: int


class StructNested(Struct):
    inner: StructInner
    outer: str


def test_nested_struct(app, assert_parse_args):
    """Test nested struct."""

    @app.default
    def cmd(data: Annotated[StructNested, Parameter(name="*")]):
        return data

    assert_parse_args(
        cmd,
        "--inner.name Alice --inner.age 25 --outer test",
        data=StructNested(inner=StructInner(name="Alice", age=25), outer="test"),
    )
