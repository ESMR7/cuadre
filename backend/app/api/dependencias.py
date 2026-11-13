"""Dependencias de la API: sesión de base, reloj, token y clave de idempotencia."""

import re
from collections.abc import Iterator
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session, sessionmaker

from app.db.sesion import crear_fabrica, obtener_motor
from app.domain.errores import FaltaClaveIdempotencia, NoAutenticado

_BEARER = re.compile(r"bearer (\S+)", re.IGNORECASE)


@lru_cache
def _fabrica() -> sessionmaker[Session]:
    return crear_fabrica(obtener_motor())


def obtener_sesion_bd() -> Iterator[Session]:
    """Una sesión por petición. No hace commit: el servicio es dueño de la transacción."""
    with _fabrica()() as sesion:
        yield sesion


def obtener_ahora() -> datetime:
    """Única lectura del reloj en la API, una vez por petición (regla 10)."""
    return datetime.now(UTC)


def obtener_token(authorization: Annotated[str | None, Header()] = None) -> str:
    """Token de `Authorization: Bearer <token>`. Ausente o mal formada: 401."""
    coincidencia = _BEARER.fullmatch(authorization or "")
    if coincidencia is None:
        raise NoAutenticado()
    return coincidencia.group(1)


def obtener_clave(
    idempotency_key: Annotated[str | None, Header()] = None,
) -> UUID:
    """Idempotency-Key: ausente da 400; si no es un UUID v4, 422 (SPEC 9.1)."""
    if idempotency_key is None:
        raise FaltaClaveIdempotencia()
    try:
        clave = UUID(idempotency_key)
    except ValueError:
        clave = None
    # UUID() acepta llaves, guiones opcionales y prefijo urn:; se exige la forma canónica.
    if clave is None or clave.version != 4 or str(clave) != idempotency_key.lower():
        raise RequestValidationError(
            [{"loc": ("header", "Idempotency-Key"), "msg": "", "type": "uuid"}]
        )
    return clave


SesionBD = Annotated[Session, Depends(obtener_sesion_bd)]
Ahora = Annotated[datetime, Depends(obtener_ahora)]
Token = Annotated[str, Depends(obtener_token)]
Clave = Annotated[UUID, Depends(obtener_clave)]
