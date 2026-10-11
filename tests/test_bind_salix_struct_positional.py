import salix


def test_bind_salix_struct_positional(app, assert_parse_args):
    class Employee(salix.Struct):
        name: str
        id: int = 3

    @app.command
    def foo(user: Employee):
        pass

    assert_parse_args(
        foo,
        'foo --user.name="John Smith" --user.id=100',
        Employee(name="John Smith", id=100),
    )

    assert_parse_args(
        foo,
        'foo "John Smith" 100',
        Employee(name="John Smith", id=100),
    )


def test_bind_salix_struct_positional_var_positional(app, assert_parse_args):
    class Employee(salix.Struct):
        name: str
        id: int

    @app.command
    def foo(*users: Employee):
        pass

    assert_parse_args(
        foo,
        'foo "John Smith" 100 "Mary Jones" 200',
        Employee(name="John Smith", id=100),
        Employee(name="Mary Jones", id=200),
    )

