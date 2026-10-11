from typing import Any

import salix
from salix import Struct

from cyclopts.utils import UNSET


class Token(Struct, frozen=True):
    """Tracks how a user supplied a value to the application."""

    keyword: str | None = None
    value: str = ""
    source: str = ""
    index: int = 0
    keys: tuple[str, ...] = ()
    implicit_value: Any = UNSET

    @property
    def address(self) -> tuple[tuple[str, ...], int]:
        """Hashable subkey destination address for this token."""
        return (self.keys, self.index)

    def evolve(self, **kwargs) -> "Token":
        return salix.replace(self, **kwargs)
