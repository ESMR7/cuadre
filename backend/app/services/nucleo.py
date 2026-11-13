"""Casos de uso cargar y transferir (SPEC 5.4 y 5.5).

Orden dentro de cada intento (SPEC 2.4): autenticar sin bloqueo; reservar la
clave; validar lo que no depende del estado; bloquear cuentas por id
ascendente; leer el estado ya bloqueado; decidir; escribir en el libro;
completar la clave; commit. Cualquier excepción revierte todo, clave incluida.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.idempotencia import hash_peticion
from app.domain.validaciones import (
    validar_destino_distinto,
    validar_monto,
    validar_saldo_suficiente,
)
from app.services.idempotencia import (
    completar_clave,
    reservar_clave,
    respuesta_guardada,
)
from app.services.libro import (
    TransaccionRegistrada,
    bloquear_cuentas,
    registrar_transaccion,
)
from app.services.reintentos import ejecutar_con_reintentos
from app.services.sesiones import autenticar

CUENTA_SISTEMA = "sistema"


def cargar(
    sesion: Session, token: str, clave: UUID, monto: int, ahora: datetime
) -> TransaccionRegistrada:
    return ejecutar_con_reintentos(
        "cargar", lambda: _cargar_una_vez(sesion, token, clave, monto, ahora)
    )


def transferir(
    sesion: Session,
    token: str,
    clave: UUID,
    destino: str,
    monto: int,
    ahora: datetime,
) -> TransaccionRegistrada:
    return ejecutar_con_reintentos(
        "transferir",
        lambda: _transferir_una_vez(sesion, token, clave, destino, monto, ahora),
    )


def _cargar_una_vez(
    sesion: Session, token: str, clave: UUID, monto: int, ahora: datetime
) -> TransaccionRegistrada:
    with sesion.begin():
        cuenta = autenticar(sesion, token, ahora).cuenta_id
        hash_ = hash_peticion("cargar", {}, {"monto": monto})
        if not reservar_clave(sesion, cuenta, clave, "cargar", hash_, ahora):
            return respuesta_guardada(sesion, cuenta, clave, hash_)
        validar_monto(monto)
        cuentas = bloquear_cuentas(
            sesion, {CUENTA_SISTEMA: "sistema", cuenta: "personal"}
        )
        respuesta = registrar_transaccion(
            sesion, "carga", cuentas[CUENTA_SISTEMA], cuentas[cuenta], monto, ahora
        )
        completar_clave(sesion, cuenta, clave, respuesta.id)
    return respuesta


def _transferir_una_vez(
    sesion: Session,
    token: str,
    clave: UUID,
    destino: str,
    monto: int,
    ahora: datetime,
) -> TransaccionRegistrada:
    with sesion.begin():
        cuenta = autenticar(sesion, token, ahora).cuenta_id
        hash_ = hash_peticion("transferir", {}, {"destino": destino, "monto": monto})
        if not reservar_clave(sesion, cuenta, clave, "transferir", hash_, ahora):
            return respuesta_guardada(sesion, cuenta, clave, hash_)
        validar_monto(monto)
        # Antes de bloquear: si no, la búsqueda daría una sola cuenta (SPEC 5.5).
        validar_destino_distinto(cuenta, destino)
        cuentas = bloquear_cuentas(sesion, {cuenta: "personal", destino: "personal"})
        validar_saldo_suficiente(cuentas[cuenta].saldo, monto)
        respuesta = registrar_transaccion(
            sesion, "transferencia", cuentas[cuenta], cuentas[destino], monto, ahora
        )
        completar_clave(sesion, cuenta, clave, respuesta.id)
    return respuesta
