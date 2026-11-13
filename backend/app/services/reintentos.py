"""Envoltorio de reintentos ante 40P01 y 40001 (SPEC 2.3).

3 intentos en total. El error se identifica por `error.orig.sqlstate`, nunca
por el texto. El log solo lleva caso de uso, código e intento.

El contador es una métrica para las pruebas (un 40P01 significa que se rompió
el orden de bloqueo, SPEC 10.4). Su Lock protege solo el contador, nunca un
saldo: los saldos los protege PostgreSQL.
"""

import logging
import threading
from collections import Counter
from collections.abc import Callable
from typing import Final, TypeVar

from sqlalchemy.exc import DBAPIError

from app.domain.errores import ReintentosAgotados

T = TypeVar("T")

CODIGOS_REINTENTABLES: Final[frozenset[str]] = frozenset({"40P01", "40001"})
INTENTOS_MAXIMOS: Final[int] = 3

logger = logging.getLogger(__name__)

_contador: Counter[str] = Counter()
_cerrojo_contador = threading.Lock()


def _codigo_reintentable(error: DBAPIError) -> str | None:
    codigo = getattr(error.orig, "sqlstate", None)
    return codigo if codigo in CODIGOS_REINTENTABLES else None


def ejecutar_con_reintentos(caso_de_uso: str, funcion: Callable[[], T]) -> T:
    """Ejecuta `funcion` (el caso de uso completo, con su transacción).

    Ante 40P01 o 40001 la repite, hasta 3 intentos en total; después lanza
    ReintentosAgotados. Cualquier otro error se propaga sin reintentar.
    """
    for intento in range(1, INTENTOS_MAXIMOS + 1):
        try:
            return funcion()
        except DBAPIError as error:
            codigo = _codigo_reintentable(error)
            if codigo is None:
                raise
            with _cerrojo_contador:
                _contador[codigo] += 1
            logger.warning(
                "Reintento: caso=%s codigo=%s intento=%d", caso_de_uso, codigo, intento
            )
    raise ReintentosAgotados()


def reintentos_por_codigo() -> dict[str, int]:
    """Copia del contador: modificarla no cambia el original."""
    with _cerrojo_contador:
        return dict(_contador)


def reiniciar_contador() -> None:
    with _cerrojo_contador:
        _contador.clear()
