"""Claves de idempotencia (SPEC 2.5 y 3.4)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.modelos import ClaveIdempotencia
from app.domain.errores import ClaveReutilizada
from app.services.libro import TransaccionRegistrada, leer_transaccion


class ClaveSinTransaccion(Exception):
    """Clave confirmada de cargar o transferir sin transaccion_id: estado
    interno imposible (L7). No es un ErrorDominio.
    """


def _de(cuenta: str, clave: UUID):
    return (
        ClaveIdempotencia.cuenta_solicitante_id == cuenta,
        ClaveIdempotencia.clave == clave,
    )


def reservar_clave(
    sesion: Session,
    cuenta: str,
    clave: UUID,
    operacion: str,
    hash_: str,
    ahora: datetime,
) -> bool:
    """INSERT ... ON CONFLICT DO NOTHING RETURNING. True si la clave es nueva.

    Si otra transacción tiene la misma clave sin confirmar, este INSERT espera
    en el índice único hasta que confirme o revierta.
    """
    insertada = sesion.execute(
        insert(ClaveIdempotencia)
        .values(
            cuenta_solicitante_id=cuenta,
            clave=clave,
            operacion=operacion,
            hash_peticion=hash_,
            creado_en=ahora,
        )
        .on_conflict_do_nothing(
            index_elements=[
                ClaveIdempotencia.cuenta_solicitante_id,
                ClaveIdempotencia.clave,
            ]
        )
        .returning(ClaveIdempotencia.clave)
    ).scalar_one_or_none()
    return insertada is not None


def respuesta_guardada(
    sesion: Session, cuenta: str, clave: UUID, hash_: str
) -> TransaccionRegistrada:
    """Respuesta original reconstruida desde el libro.

    Otro hash: ClaveReutilizada. Mismo hash sin transacción: ClaveSinTransaccion.
    """
    fila = sesion.execute(
        select(ClaveIdempotencia.hash_peticion, ClaveIdempotencia.transaccion_id).where(
            *_de(cuenta, clave)
        )
    ).one()
    if fila.hash_peticion != hash_:
        raise ClaveReutilizada()
    if fila.transaccion_id is None:
        raise ClaveSinTransaccion("La clave confirmada no tiene transacción.")
    return leer_transaccion(sesion, fila.transaccion_id)


def completar_clave(
    sesion: Session, cuenta: str, clave: UUID, transaccion_id: int
) -> None:
    sesion.execute(
        update(ClaveIdempotencia)
        .where(*_de(cuenta, clave))
        .values(transaccion_id=transaccion_id)
    )
