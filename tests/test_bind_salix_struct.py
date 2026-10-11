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


def test_a_struct_class_whose_field_infos_were_read_can_still_be_collected():
    import gc
    import weakref

    from cyclopts.field_info import _struct_field_infos

    built = type(salix.Struct)("Built", (salix.Struct,), {"__annotations__": {"x": int}})
    assert list(_struct_field_infos(built)) == ["x"]
    collected = weakref.ref(built)

    del built
    gc.collect()

    assert collected() is None
