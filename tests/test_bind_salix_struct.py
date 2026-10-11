import salix

from cyclopts.argument import ArgumentCollection


class Point(salix.Struct):
    x: int
    y: int = 0


def test_salix_struct_missing_keys_checker_reports_required_field():
    def foo(point: Point):
        pass

    argument = ArgumentCollection._from_callable(foo)[0]
    assert argument._missing_keys_checker(argument, {"y": 1}) == ["x"]
    assert argument._missing_keys_checker(argument, {"x": 1}) == []
