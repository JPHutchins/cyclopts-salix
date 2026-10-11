import inspect
import sys
import weakref
from typing import (  # noqa: F401
    Annotated,
    Any,
    ClassVar,
    Optional,
    get_args,
    get_origin,
    get_type_hints,
)

import salix
from salix import Struct

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

from cyclopts.annotations import (
    NotRequired,
    Required,
    is_annotated,
    is_enum,
    is_enum_flag,
    is_pydantic,
    is_pydantic_secret,
    is_salix_struct,
    is_typeddict,
    resolve,
    resolve_annotated,
    resolve_optional,
)
from cyclopts.utils import UNSET, is_builtin

POSITIONAL_OR_KEYWORD = inspect.Parameter.POSITIONAL_OR_KEYWORD
POSITIONAL_ONLY = inspect.Parameter.POSITIONAL_ONLY
KEYWORD_ONLY = inspect.Parameter.KEYWORD_ONLY
VAR_POSITIONAL = inspect.Parameter.VAR_POSITIONAL
VAR_KEYWORD = inspect.Parameter.VAR_KEYWORD


def _replace_annotated_type(src_type, dst_type):
    if not is_annotated(src_type):
        return dst_type
    return Annotated[(dst_type,) + get_args(src_type)[1:]]  # pyright: ignore


class FieldInfo(Struct, frozen=True):
    """Extension of :class:`inspect.Parameter`."""

    names: tuple[str, ...] = ()
    kind: inspect._ParameterKind = inspect.Parameter.POSITIONAL_OR_KEYWORD

    required: bool = False
    default: Any = inspect.Parameter.empty
    annotation: Any = inspect.Parameter.empty

    help: str | None = None
    """Can be populated by additional metadata from another library; e.g. ``pydantic.FieldInfo.description``."""

    ###################
    # Class Variables #
    ###################
    empty: ClassVar = inspect.Parameter.empty
    POSITIONAL_OR_KEYWORD: ClassVar = inspect.Parameter.POSITIONAL_OR_KEYWORD
    POSITIONAL_ONLY: ClassVar = inspect.Parameter.POSITIONAL_ONLY
    KEYWORD_ONLY: ClassVar = inspect.Parameter.KEYWORD_ONLY
    VAR_POSITIONAL: ClassVar = inspect.Parameter.VAR_POSITIONAL
    VAR_KEYWORD: ClassVar = inspect.Parameter.VAR_KEYWORD
    POSITIONAL: ClassVar[frozenset[inspect._ParameterKind]] = frozenset(
        {POSITIONAL_OR_KEYWORD, POSITIONAL_ONLY, VAR_POSITIONAL}
    )
    KEYWORD: ClassVar[frozenset[inspect._ParameterKind]] = frozenset({POSITIONAL_OR_KEYWORD, KEYWORD_ONLY, VAR_KEYWORD})

    @classmethod
    def from_iparam(cls, iparam: inspect.Parameter, *, annotation: Any = UNSET, required: bool | None = None) -> Self:
        if required is None:
            required = (
                iparam.default is iparam.empty
                and iparam.kind != iparam.VAR_KEYWORD
                and iparam.kind != iparam.VAR_POSITIONAL
            )

        return cls(
            names=(iparam.name,),
            annotation=iparam.annotation if annotation is UNSET else annotation,
            kind=iparam.kind,
            default=iparam.default,
            required=required,
        )

    @property
    def hint(self):
        """Annotation with Optional-removed and cyclopts type-inferring."""
        hint = self.annotation
        if hint is inspect.Parameter.empty or resolve(hint) is Any:
            hint = _replace_annotated_type(
                hint, str if self.default is inspect.Parameter.empty or self.default is None else type(self.default)
            )
        hint = resolve_optional(hint)
        return hint

    @property
    def name(self):
        """The **first** provided name."""
        return self.names[0]

    @property
    def is_positional(self) -> bool:
        return self.kind in self.POSITIONAL

    @property
    def is_positional_only(self) -> bool:
        return self.kind in (POSITIONAL_ONLY, VAR_POSITIONAL)

    @property
    def is_keyword(self) -> bool:
        return self.kind in self.KEYWORD

    @property
    def is_keyword_only(self) -> bool:
        return self.kind in (KEYWORD_ONLY, VAR_KEYWORD)

    def evolve(self, **kwargs):
        return salix.replace(self, **kwargs)


def _typed_dict_field_infos(typeddict) -> dict[str, FieldInfo]:
    # The ``__required_keys__`` and ``__optional_keys__`` attributes of TypedDict are kind of broken in <cp3.11.
    out = {}
    for name, annotation in get_type_hints(typeddict, include_extras=True).items():
        origin = get_origin(resolve_annotated(annotation))
        if origin is Required:
            required = True
        elif origin is NotRequired:
            required = False
        elif typeddict.__total__:  # Fields are REQUIRED by default.
            required = True
        else:  # Fields are OPTIONAL by default
            required = False
        out[name] = FieldInfo((name,), FieldInfo.KEYWORD_ONLY, annotation=annotation, required=required)
    return out


def _generic_class_field_infos(
    f,
    include_var_positional=False,
    include_var_keyword=False,
) -> dict[str, FieldInfo]:
    out = {}
    for name, field_info in signature_parameters(f.__init__).items():
        if field_info.name == "self":
            continue
        if not include_var_positional and field_info.kind is field_info.VAR_POSITIONAL:
            continue
        if not include_var_keyword and field_info.kind is field_info.VAR_KEYWORD:
            continue
        out[name] = field_info
    return out


def _pydantic_field_infos(model) -> dict[str, FieldInfo]:
    from pydantic_core import PydanticUndefined

    out = {}
    for python_name, pydantic_field in model.model_fields.items():
        names = []
        if pydantic_field.alias:
            # Register a CLI name only if the model would actually accept it during
            # validation (cyclopts builds the model via TypeAdapter.validate_python).
            #   * validate_by_name  -> field names are accepted.
            #   * validate_by_alias -> aliases are accepted (defaults to True).
            # populate_by_name is the pre-2.11 spelling of validate_by_name; it is not
            # recommended in pydantic 2.11+ and is slated for removal in pydantic v3, so
            # we honor both across the supported pydantic range. pydantic forbids both
            # validate_by_* being False, so at least one name is always registered.
            validate_by_name = model.model_config.get("validate_by_name", False) or model.model_config.get(
                "populate_by_name", False
            )
            validate_by_alias = model.model_config.get("validate_by_alias", True)

            if validate_by_name:
                names.append(python_name)
            if validate_by_alias:
                names.append(pydantic_field.alias)

                # Add legacy-compatible CLI form if not already present.
                # This allows both "user-name" (new) and "username" (legacy) to work as CLI options.
                # Old transform behavior: alias.lower() (no pascal_to_snake)
                # New transform behavior: _pascal_to_snake(alias).lower()
                legacy_form = pydantic_field.alias.lower()
                if legacy_form not in names:
                    names.append(legacy_form)
        else:
            names.append(python_name)

        # Extract Field with description from metadata
        help = pydantic_field.description or None
        for meta in pydantic_field.metadata:
            if hasattr(meta, "description") and meta.description:
                help = meta.description

        # Pydantic places ``Annotated`` data into pydantic.FieldInfo.metadata, while
        # pydantic.FieldInfo.annotation contains the "real" resolved type-hint.
        # We have to re-combine them into a single Annotated hint.
        # For discriminated unions, pydantic stores discriminator separately (not in metadata),
        # so include pydantic_field itself to preserve the discriminator attribute.
        if pydantic_field.discriminator:
            annotation = Annotated[(pydantic_field.annotation, pydantic_field) + tuple(pydantic_field.metadata)]  # pyright: ignore
        elif pydantic_field.metadata:
            annotation = Annotated[(pydantic_field.annotation,) + tuple(pydantic_field.metadata)]  # pyright: ignore
        else:
            annotation = pydantic_field.annotation

        if pydantic_field.default_factory is not None:
            try:
                default = pydantic_field.get_default(call_default_factory=True)
            except (TypeError, ValueError):
                # Factories that require validated data cannot be invoked during introspection;
                # treat those fields as having no introspectable default.
                default = FieldInfo.empty
        elif pydantic_field.default is PydanticUndefined:
            default = FieldInfo.empty
        else:
            default = pydantic_field.default

        out[python_name] = FieldInfo(
            names=tuple(names),
            kind=inspect.Parameter.KEYWORD_ONLY if pydantic_field.kw_only else inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=annotation,
            default=default,
            required=pydantic_field.is_required(),
            help=help,
        )
    return out


_STRUCT_TYPE_HINTS: "weakref.WeakKeyDictionary[type, dict[str, Any]]" = weakref.WeakKeyDictionary()


def _struct_type_hints(hint) -> dict[str, Any]:
    cached = _STRUCT_TYPE_HINTS.get(hint)
    if cached is None:
        cached = _STRUCT_TYPE_HINTS[hint] = get_type_hints(hint, include_extras=True)
    return cached


def _struct_field_infos(hint) -> dict[str, FieldInfo]:
    type_hints = _struct_type_hints(hint)
    return {
        field.name: FieldInfo(
            names=(field.name,),
            kind=FieldInfo.KEYWORD_ONLY if field.kw_only else FieldInfo.POSITIONAL_OR_KEYWORD,
            required=field.default is salix.MISSING,
            annotation=type_hints.get(field.name, FieldInfo.empty),
            default=FieldInfo.empty if field.default is salix.MISSING else field.default,
        )
        for field in salix.fields(hint)
    }


def _enum_flag_field_infos(enum_flag) -> dict[str, FieldInfo]:
    """Extract field infos from a Flag enum, treating each member as a boolean field."""
    out = {}
    for member_name in enum_flag.__members__:
        out[member_name] = FieldInfo(
            names=(member_name,),
            kind=FieldInfo.KEYWORD_ONLY,
            # The Enum member should NEVER have a type-annotation.
            # Thusly, it by definition cannot have an Annotated[...].
            # see: https://typing.python.org/en/latest/spec/enums.html#defining-members
            annotation=bool,  # Each flag acts as a boolean
            default=False,  # Default to False (not included in combination)
            required=False,  # All flags are optional
        )
    return out


def get_field_infos(hint) -> dict[str, FieldInfo]:
    # Early return for builtin types (int, str, etc.) to avoid expensive introspection.
    # Provides ~5-6x speedup for argument parsing by skipping signature_parameters() calls.
    if is_builtin(hint):
        return {}

    # Pydantic secret types (SecretStr, SecretBytes) should be treated as simple types
    if is_pydantic_secret(hint):
        return {}

    # NewType is a runtime identity function that returns its argument unchanged.
    # Use the field_infos of the underlying supertype instead of NewType's misleading __init__.
    if hasattr(hint, "__supertype__"):
        return get_field_infos(hint.__supertype__)

    if is_salix_struct(hint):
        return _struct_field_infos(hint)
    elif is_pydantic(hint):
        return _pydantic_field_infos(hint)
    elif is_typeddict(hint):
        return _typed_dict_field_infos(hint)
    elif is_enum_flag(hint):
        return _enum_flag_field_infos(hint)
    elif is_enum(hint):
        # Plain (non-Flag) Enums are leaf choice-sets converted by member name;
        # a user-defined ``__init__`` must not cause decomposition into children.
        return {}
    else:
        return _generic_class_field_infos(hint)


def signature_parameters(f: Any) -> dict[str, FieldInfo]:
    if "functools" in sys.modules:
        from functools import partial

        func = f.func if isinstance(f, partial) else f
    else:
        func = f

    type_hints = get_type_hints(func, include_extras=True)

    out = {}
    for name, iparam in inspect.signature(f).parameters.items():
        annotation = type_hints.get(name, iparam.annotation)
        out[name] = FieldInfo.from_iparam(iparam, annotation=annotation)

    if inspect.isclass(func):
        # ``inspect.signature`` on a class surfaces raw ``__init__`` defaults, which can be
        # library-private sentinels for factory fields (e.g. pydantic's generated ``__signature__``).
        # ``get_field_infos`` already resolves defaults per-library; merge its
        # default/requiredness over the raw signature values.
        for name, field_info in get_field_infos(func).items():
            for candidate in field_info.names or (name,):
                if candidate in out:
                    out[candidate] = out[candidate].evolve(default=field_info.default, required=field_info.required)

    return out
