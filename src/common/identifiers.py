from __future__ import annotations

import re

from src.common.errors import ConfigurationError

_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]*$")


def safe_oracle_identifier(value: str, label: str = "identifier") -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ConfigurationError(f"Invalid Oracle {label}: {value!r}")
    return value.upper()
