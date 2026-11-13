"""Aportar, retirarse y confirmar (SPEC 6.5 a 6.8).

Orden dentro de cada intento (SPEC 2.4 y 8.2): autenticar sin bloqueo;
reservar la clave (aportar y retirarse); bloquear la fila de la bolsa con
FOR UPDATE; leer bolsa y participantes; revisar participante (403), estado
de la bolsa, plazo y estado del participante (las tres últimas en domain/);
decidir qué cuentas bloquear; bloquearlas por id ascendente con FOR NO KEY
UPDATE; escribir en el libro; commit. Una sola bolsa por transacción.

Todo el dinero pasa por `registrar_transaccion` del libro (regla 2).
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app.db.modelos import Bolsa, Cuenta, Participante
from app.domain import bolsas as dominio
from app.domain.bolsas import EstadoBolsa, EstadoParticipante
from app.domain.errores import NoEncontrado, SinPermiso
from app.domain.idempotencia import hash_peticion
from app.domain.validaciones import validar_saldo_suficiente
from app.services.idempotencia import (
    completar_clave,
    reservar_clave,
    respuesta_guardada,
    transaccion_guardada,
)
from app.services.libro import (
    TransaccionRegistrada,
    bloquear_cuentas,
    deuda_participante,
    registrar_transaccion,
)
from app.services.reintentos import ejecutar_con_reintentos
from app.services.sesiones import autenticar


class BolsaInconsistente(Exception):
    """Estado interno imposible: deuda distinta de la parte, saldo distinto de
    la suma de los pagados o cierre con saldo distinto de 0. No es un
    ErrorDominio: da 500 y revierte.
    """


@dataclass(frozen=True)
class ResultadoRetiro:
    devolucion: TransaccionRegistrada | None


@dataclass(frozen=True)
class ResultadoConfirmar:
    estado_bolsa: str
    mi_estado: str


Estados = dict[str, EstadoParticipante]

_SALDO = text("SELECT saldo FROM cuentas WHERE id = :cuenta")
_PARTICIPANTES = text(
    "SELECT cuenta_id, parte, estado FROM participantes WHERE bolsa_id = :bolsa"
)


# --- Casos de uso ------------------------------------------------------------


def aportar(
    sesion: Session, token: str, clave: UUID, bolsa_id: UUID, ahora: datetime
) -> TransaccionRegistrada:
    return ejecutar_con_reintentos(
        "aportar", lambda: _aportar_una_vez(sesion, token, clave, bolsa_id, ahora)
    )


def retirarse(
    sesion: Session, token: str, clave: UUID, bolsa_id: UUID, ahora: datetime
) -> ResultadoRetiro:
    return ejecutar_con_reintentos(
        "retirarse",
        lambda: _retirarse_una_vez(sesion, token, clave, bolsa_id, ahora),
    )


def confirmar(
    sesion: Session, token: str, bolsa_id: UUID, ahora: datetime
) -> ResultadoConfirmar:
    return ejecutar_con_reintentos(
        "confirmar", lambda: _confirmar_una_vez(sesion, token, bolsa_id, ahora)
    )


def _aportar_una_vez(
    sesion: Session, token: str, clave: UUID, bolsa_id: UUID, ahora: datetime
) -> TransaccionRegistrada:
    with sesion.begin():
        yo = autenticar(sesion, token, ahora).cuenta_id
        hash_ = hash_peticion("aportar", {"bolsa_id": str(bolsa_id)}, {})
        if not reservar_clave(sesion, yo, clave, "aportar", hash_, ahora):
            return respuesta_guardada(sesion, yo, clave, hash_)
        bolsa = _bloquear_bolsa(sesion, bolsa_id)
        partes, estados = _leer_participantes(sesion, bolsa_id, yo)
        r = dominio.aportar(
            EstadoBolsa(bolsa.estado), estados, yo, bolsa.fecha_limite, ahora
        )
        # La cuenta objetivo solo se bloquea si el aporte completa (6.5).
        tipos = {yo: "personal", bolsa.cuenta_id: "bolsa"}
        if r.completa:
            tipos[bolsa.cuenta_objetivo_id] = "personal"
        cuentas = bloquear_cuentas(sesion, tipos)
        validar_saldo_suficiente(cuentas[yo].saldo, partes[yo])
        aporte = registrar_transaccion(
            sesion, "aporte", cuentas[yo], cuentas[bolsa.cuenta_id], partes[yo], ahora
        )
        _escribir_estados(sesion, bolsa_id, estados, r.participantes)
        if r.completa:
            _transferencia_final(sesion, bolsa, cuentas, partes, r.participantes, ahora)
        completar_clave(sesion, yo, clave, aporte.id)
    return aporte


def _retirarse_una_vez(
    sesion: Session, token: str, clave: UUID, bolsa_id: UUID, ahora: datetime
) -> ResultadoRetiro:
    with sesion.begin():
        yo = autenticar(sesion, token, ahora).cuenta_id
        hash_ = hash_peticion("retirarse", {"bolsa_id": str(bolsa_id)}, {})
        if not reservar_clave(sesion, yo, clave, "retirarse", hash_, ahora):
            return ResultadoRetiro(transaccion_guardada(sesion, yo, clave, hash_))
        bolsa = _bloquear_bolsa(sesion, bolsa_id)
        partes, estados = _leer_participantes(sesion, bolsa_id, yo)
        r = dominio.retirarse(
            EstadoBolsa(bolsa.estado), estados, yo, bolsa.fecha_limite, ahora
        )
        devolucion = None
        if r.habia_pagado:
            cuentas = bloquear_cuentas(
                sesion, {yo: "personal", bolsa.cuenta_id: "bolsa"}
            )
            # Deuda desde el libro, por tipo (3.6): debe ser exactamente su parte.
            deuda = deuda_participante(sesion, bolsa.cuenta_id, yo)
            if deuda != partes[yo]:
                raise BolsaInconsistente(
                    f"Deuda {deuda} distinta de la parte {partes[yo]}."
                )
            devolucion = registrar_transaccion(
                sesion,
                "devolucion",
                cuentas[bolsa.cuenta_id],
                cuentas[yo],
                deuda,
                ahora,
            )
        _escribir_estados(sesion, bolsa_id, estados, r.participantes)
        if r.cierra:
            _cerrar_en_cero(sesion, bolsa)
        if devolucion is not None:
            completar_clave(sesion, yo, clave, devolucion.id)
        # Sin devolución, la clave queda con transaccion_id nulo (2.5 y L7).
    return ResultadoRetiro(devolucion)


def _confirmar_una_vez(
    sesion: Session, token: str, bolsa_id: UUID, ahora: datetime
) -> ResultadoConfirmar:
    """Sin clave de idempotencia (SPEC 6.7 y 9.4)."""
    with sesion.begin():
        yo = autenticar(sesion, token, ahora).cuenta_id
        bolsa = _bloquear_bolsa(sesion, bolsa_id)
        partes, estados = _leer_participantes(sesion, bolsa_id, yo)
        r = dominio.confirmar(
            EstadoBolsa(bolsa.estado), estados, yo, bolsa.fecha_limite, ahora
        )
        cuentas = {}
        if r.completa:
            cuentas = bloquear_cuentas(
                sesion, {bolsa.cuenta_id: "bolsa", bolsa.cuenta_objetivo_id: "personal"}
            )
        _escribir_estados(sesion, bolsa_id, estados, r.participantes)
        if r.completa:
            _transferencia_final(sesion, bolsa, cuentas, partes, r.participantes, ahora)
        respuesta = ResultadoConfirmar(
            estado_bolsa=r.estado_bolsa.value, mi_estado=r.participantes[yo].value
        )
    return respuesta


# --- Pasos comunes -----------------------------------------------------------


def _bloquear_bolsa(sesion: Session, bolsa_id: UUID) -> Bolsa:
    """FOR UPDATE sobre la fila de la bolsa, con populate_existing (2.4)."""
    bolsa = sesion.execute(
        select(Bolsa)
        .where(Bolsa.id == bolsa_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if bolsa is None:
        raise NoEncontrado("La bolsa no existe.")
    return bolsa


def _leer_participantes(
    sesion: Session, bolsa_id: UUID, yo: str
) -> tuple[dict[str, int], Estados]:
    """Partes y estados, leídos bajo el bloqueo de la bolsa. Sin mí: 403.

    La pertenencia se revisa antes que el estado de la bolsa (6.5).
    """
    filas = sesion.execute(_PARTICIPANTES, {"bolsa": bolsa_id}).all()
    partes = {f.cuenta_id: f.parte for f in filas}
    estados = {f.cuenta_id: EstadoParticipante(f.estado) for f in filas}
    if yo not in estados:
        raise SinPermiso("No figura en la bolsa.")
    return partes, estados


def _escribir_estados(
    sesion: Session, bolsa_id: UUID, antes: Estados, despues: Estados
) -> None:
    """Solo cambia `estado`, y solo en las filas que cambian. Nunca la parte."""
    for cuenta, estado in despues.items():
        if antes[cuenta] != estado:
            sesion.execute(
                update(Participante)
                .where(
                    Participante.bolsa_id == bolsa_id, Participante.cuenta_id == cuenta
                )
                .values(estado=estado.value)
            )


def _leer_saldo(sesion: Session, cuenta: str) -> int:
    """Sentencia nueva: el objeto Cuenta en memoria queda viejo tras el UPDATE
    relativo del libro.
    """
    return sesion.execute(_SALDO, {"cuenta": cuenta}).scalar_one()


def _transferencia_final(
    sesion: Session,
    bolsa: Bolsa,
    cuentas: dict[str, Cuenta],
    partes: dict[str, int],
    estados: Estados,
    ahora: datetime,
) -> None:
    """Envía el saldo de la bolsa a la cuenta objetivo y la cierra (6.8).

    Exige, como 7.4 paso 3, que el saldo sea exactamente la suma de las
    partes de quienes están en `pagado`. Las cuentas ya están bloqueadas.
    """
    saldo = _leer_saldo(sesion, bolsa.cuenta_id)
    esperado = sum(
        partes[c] for c, e in estados.items() if e == EstadoParticipante.PAGADO
    )
    if saldo <= 0 or saldo != esperado:
        raise BolsaInconsistente(f"Saldo {saldo} distinto de lo pagado {esperado}.")
    registrar_transaccion(
        sesion,
        "transferencia_final",
        cuentas[bolsa.cuenta_id],
        cuentas[bolsa.cuenta_objetivo_id],
        saldo,
        ahora,
    )
    _cerrar_en_cero(sesion, bolsa)


def _cerrar_en_cero(sesion: Session, bolsa: Bolsa) -> None:
    """Última defensa: una bolsa solo se cierra con saldo 0 (6.1)."""
    saldo = _leer_saldo(sesion, bolsa.cuenta_id)
    if saldo != 0:
        raise BolsaInconsistente(f"La bolsa {bolsa.id} tiene saldo {saldo} al cerrar.")
    sesion.execute(
        update(Bolsa)
        .where(Bolsa.id == bolsa.id)
        .values(estado=EstadoBolsa.CERRADA.value)
    )
