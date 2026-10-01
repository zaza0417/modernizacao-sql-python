from modernizer.dialects.base import Dialect
from modernizer.dialects.postgres import PostgresDialect

_DIALECTS: dict[str, Dialect] = {"postgres": PostgresDialect()}


def get_dialect(name: str) -> Dialect:
    try:
        return _DIALECTS[name]
    except KeyError:
        raise ValueError(f"Dialeto não suportado: {name}") from None