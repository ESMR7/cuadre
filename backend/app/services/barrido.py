"""Barrido de bolsas vencidas y en liquidación (SPEC 2.8 y 7.4, T14).

Tres pasos, cada uno en su propia transacción que empieza bloqueando la fila
de la bolsa y releyendo su estado: preparar, devolver (uno por participante)
y cerrar. `procesar_vencidas` lista las candidatas sin bloquear y llama a los
pasos en orden; una bolsa que falla se registra y no detiene a las demás.
Nada aquí lee el reloj: `ahora` llega como parámetro.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import text, update
from sqlalchemy.orm import Session, sessionmaker

from app.db.modelos import Bolsa
from app.domain import bolsas as dominio
from app.domain.bolsas import EstadoBolsa, EstadoParticipante
from app.services.libro import (
    TransaccionRegistrada,
    bloquear_cuentas,
    deuda_participante,
    registrar_transaccion,
)
from app.services.operaciones_bolsa import (
    BolsaInconsistente,
    _bloquear_bolsa,
    _cerrar_en_cero,
    _escribir_estados,
    _leer_saldo,
    _transferencia_final,
)
from app.services.reintentos import ejecutar_con_reintentos

log = logging.getLogger("app.barrido")

_CANDIDATAS = text(
    """
    SELECT id
    FROM bolsas
    WHERE (estado IN ('abierta', 'cancelada') AND fecha_limite <= :ahora)
       OR estado = 'liquidando'
    ORDER BY fecha_limite, id
    """
)
_PARTICIPANTES = text(
    "SELECT cuenta_id, parte, estado FROM participantes WHERE bolsa_id = :bolsa"
)
_RETIRADOS = text(
    "SELECT cuenta_id FROM participantes "
    "WHERE bolsa_id = :bolsa AND estado = 'retirado' ORDER BY cuenta_id"
)


@dataclass(frozen=True)
class ResumenBarrido:
    procesadas: list[UUID]
    fallidas: list[UUID]


# --- Pasos -------------------------------------------------------------------


def preparar(sesion: Session, bolsa_id: UUID, ahora: datetime) -> bool:
    """Paso 1: una bolsa vencida pasa a `liquidando`. No mueve dinero.

    Devuelve False sin tocar nada si la bolsa no está abierta o cancelada, o
    si todavía no vence.
    """
    return ejecutar_con_reintentos(
        "barrido_preparar", lambda: _preparar_una_vez(sesion, bolsa_id, ahora)
    )


def devolver(
    sesion: Session, bolsa_id: UUID, cuenta_id: str, ahora: datetime
) -> TransaccionRegistrada | None:
    """Paso 2, para un participante: devuelve su deuda, releída del libro.

    None si la bolsa no está `liquidando`, si el participante no está
    `retirado` o si su deuda es 0. Una deuda negativa es un error.
    """
    return ejecutar_con_reintentos(
        "barrido_devolver",
        lambda: _devolver_una_vez(sesion, bolsa_id, cuenta_id, ahora),
    )


def cerrar(sesion: Session, bolsa_id: UUID, ahora: datetime) -> EstadoBolsa:
    """Paso 3: cierra si no quedan deudas (7.4). Devuelve el estado final."""
    return ejecutar_con_reintentos(
        "barrido_cerrar", lambda: _cerrar_una_vez(sesion, bolsa_id, ahora)
    )


def procesar_vencidas(
    fabrica: sessionmaker[Session], ahora: datetime
) -> ResumenBarrido:
    """Lista las candidatas sin bloquear y aplica los tres pasos a cada una.

    Cada bolsa usa una sesión nueva. Una excepción en una bolsa se registra,
    la bolsa queda para el siguiente ciclo y el barrido sigue.
    """
    with fabrica() as sesion, sesion.begin():
        candidatas = list(sesion.execute(_CANDIDATAS, {"ahora": ahora}).scalars())
    procesadas: list[UUID] = []
    fallidas: list[UUID] = []
    for bolsa_id in candidatas:
        try:
            with fabrica() as sesion:
                _procesar_bolsa(sesion, bolsa_id, ahora)
            procesadas.append(bolsa_id)
        except Exception:
            log.exception("Falló el barrido de la bolsa %s", bolsa_id)
            fallidas.append(bolsa_id)
    return ResumenBarrido(procesadas, fallidas)


# --- Implementación ----------------------------------------------------------


def _procesar_bolsa(sesion: Session, bolsa_id: UUID, ahora: datetime) -> None:
    preparar(sesion, bolsa_id, ahora)
    # Lectura sin bloqueo: solo elige candidatos. `devolver` decide tras
    # bloquear y releer.
    with sesion.begin():
        retirados = list(sesion.execute(_RETIRADOS, {"bolsa": bolsa_id}).scalars())
    for cuenta_id in retirados:
        devolver(sesion, bolsa_id, cuenta_id, ahora)
    cerrar(sesion, bolsa_id, ahora)


def _preparar_una_vez(sesion: Session, bolsa_id: UUID, ahora: datetime) -> bool:
    with sesion.begin():
        bolsa = _bloquear_bolsa(sesion, bolsa_id)
        estado = EstadoBolsa(bolsa.estado)
        if estado not in {EstadoBolsa.ABIERTA, EstadoBolsa.CANCELADA}:
            return False
        if ahora < bolsa.fecha_limite:
            return False
        _, estados = _participantes(sesion, bolsa_id)
        r = dominio.preparar_liquidacion(
            estado, estados, bolsa.transferir_al_vencer, bolsa.fecha_limite, ahora
        )
        _escribir_estados(sesion, bolsa_id, estados, r.participantes)
        _cambiar_estado(sesion, bolsa_id, r.estado_bolsa)
    return True


def _devolver_una_vez(
    sesion: Session, bolsa_id: UUID, cuenta_id: str, ahora: datetime
) -> TransaccionRegistrada | None:
    with sesion.begin():
        bolsa = _bloquear_bolsa(sesion, bolsa_id)
        if bolsa.estado != EstadoBolsa.LIQUIDANDO:
            return None
        _, estados = _participantes(sesion, bolsa_id)
        if estados.get(cuenta_id) != EstadoParticipante.RETIRADO:
            return None
        cuentas = bloquear_cuentas(
            sesion, {bolsa.cuenta_id: "bolsa", cuenta_id: "personal"}
        )
        deuda = _deuda(sesion, bolsa, cuenta_id)
        if deuda == 0:
            return None
        devolucion = registrar_transaccion(
            sesion,
            "devolucion",
            cuentas[bolsa.cuenta_id],
            cuentas[cuenta_id],
            deuda,
            ahora,
        )
    return devolucion


def _cerrar_una_vez(sesion: Session, bolsa_id: UUID, ahora: datetime) -> EstadoBolsa:
    with sesion.begin():
        bolsa = _bloquear_bolsa(sesion, bolsa_id)
        estado = EstadoBolsa(bolsa.estado)
        if estado != EstadoBolsa.LIQUIDANDO:
            return estado
        partes, estados = _participantes(sesion, bolsa_id)
        hay_deudas = any(
            _deuda(sesion, bolsa, c) > 0
            for c, e in estados.items()
            if e == EstadoParticipante.RETIRADO
        )
        r = dominio.cerrar_liquidacion(
            estado, estados, bolsa.transferir_al_vencer, hay_deudas
        )
        if r.estado_bolsa == EstadoBolsa.LIQUIDANDO:
            return r.estado_bolsa
        saldo = _leer_saldo(sesion, bolsa.cuenta_id)
        if saldo == 0:
            _cerrar_en_cero(sesion, bolsa)
        elif r.completa:
            cuentas = bloquear_cuentas(
                sesion,
                {bolsa.cuenta_id: "bolsa", bolsa.cuenta_objetivo_id: "personal"},
            )
            _transferencia_final(sesion, bolsa, cuentas, partes, estados, ahora)
        else:
            raise BolsaInconsistente(
                f"La bolsa {bolsa_id} tiene saldo {saldo} sin transferencia "
                "posible; queda en liquidando para revisión."
            )
    return EstadoBolsa.CERRADA


def _participantes(
    sesion: Session, bolsa_id: UUID
) -> tuple[dict[str, int], dict[str, EstadoParticipante]]:
    """Partes y estados, leídos bajo el bloqueo de la bolsa."""
    filas = sesion.execute(_PARTICIPANTES, {"bolsa": bolsa_id}).all()
    partes = {f.cuenta_id: f.parte for f in filas}
    estados = {f.cuenta_id: EstadoParticipante(f.estado) for f in filas}
    return partes, estados


def _deuda(sesion: Session, bolsa: Bolsa, cuenta_id: str) -> int:
    """Deuda desde el libro, por tipo (3.6). Negativa: error, no mueve dinero."""
    deuda = deuda_participante(sesion, bolsa.cuenta_id, cuenta_id)
    if deuda < 0:
        raise BolsaInconsistente(
            f"Deuda negativa ({deuda}) de {cuenta_id} en la bolsa {bolsa.id}."
        )
    return deuda


def _cambiar_estado(sesion: Session, bolsa_id: UUID, estado: EstadoBolsa) -> None:
    sesion.execute(
        update(Bolsa).where(Bolsa.id == bolsa_id).values(estado=estado.value)
    )
