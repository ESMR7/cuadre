"""Ayudas para las pruebas de aportar, retirarse y confirmar (T11)."""

import itertools
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.domain.errores import ErrorDominio
from app.services.nucleo import cargar
from app.services.operaciones_bolsa import aportar, confirmar, retirarse
from app.services.reintentos import reiniciar_contador, reintentos_por_codigo
from tests.services.apoyo_bolsas import conteos, crear
from tests.services.apoyo_libro import AHORA, crear_usuario

# Fecha límite corta: el token dura 20 minutos, así que una prueba puede
# operar en `FECHA_CORTA` con el mismo token.
FECHA_CORTA = AHORA + timedelta(minutes=5)
SALDO_INICIAL = 100_000
# Cédulas distintas aunque se llame a `usuarios` varias veces en una prueba.
_CEDULAS = itertools.count(300_000)


@pytest.fixture
def sin_reintentos():
    """Cero reintentos de cualquier código (SPEC 2.3 y 10.4)."""
    reiniciar_contador()
    yield
    assert reintentos_por_codigo() == {}


def usuarios(
    bd: sessionmaker[Session], *nombres: str, saldo: int = SALDO_INICIAL
) -> dict[str, str]:
    """Registra a cada usuario, le carga `saldo` (si > 0) y devuelve los tokens."""
    tokens = {}
    for nombre in nombres:
        tokens[nombre] = crear_usuario(bd, nombre, str(next(_CEDULAS)))
        if saldo:
            cargar_saldo(bd, tokens[nombre], saldo)
    return tokens


def cargar_saldo(bd, token: str, monto: int) -> None:
    with bd() as sesion:
        cargar(sesion, token, uuid4(), monto, AHORA)


def nueva_bolsa(bd, tokens, creador="ana", **kwargs) -> UUID:
    kwargs.setdefault("fecha_limite", FECHA_CORTA)
    return crear(bd, tokens[creador], **kwargs).id


def hacer_aportar(bd, token, bolsa_id, clave=None, ahora: datetime = AHORA):
    with bd() as sesion:
        return aportar(sesion, token, clave or uuid4(), bolsa_id, ahora)


def hacer_retirarse(bd, token, bolsa_id, clave=None, ahora: datetime = AHORA):
    with bd() as sesion:
        return retirarse(sesion, token, clave or uuid4(), bolsa_id, ahora)


def hacer_confirmar(bd, token, bolsa_id, ahora: datetime = AHORA):
    with bd() as sesion:
        return confirmar(sesion, token, bolsa_id, ahora)


# --- Lecturas para verificar ---------------------------------------------


def estados(bd, bolsa_id) -> dict[str, str]:
    with bd() as sesion:
        filas = sesion.execute(
            text("SELECT cuenta_id, estado FROM participantes WHERE bolsa_id = :b"),
            {"b": bolsa_id},
        ).all()
    return {f.cuenta_id: f.estado for f in filas}


def estado_bolsa(bd, bolsa_id) -> str:
    with bd() as sesion:
        return sesion.execute(
            text("SELECT estado FROM bolsas WHERE id = :b"), {"b": bolsa_id}
        ).scalar_one()


@dataclass(frozen=True)
class Tx:
    tipo: str
    origen: str
    destino: str
    monto: int


def transacciones(bd, tipo: str | None = None) -> list[Tx]:
    with bd() as sesion:
        filas = sesion.execute(
            text(
                "SELECT tipo, cuenta_origen_id, cuenta_destino_id, monto "
                "FROM transacciones ORDER BY id"
            )
        ).all()
    todas = [Tx(f[0], f[1], f[2], f[3]) for f in filas]
    return [t for t in todas if tipo is None or t.tipo == tipo]


def saldo_de(bd, cuenta: str) -> int:
    with bd() as sesion:
        return sesion.execute(
            text("SELECT saldo FROM cuentas WHERE id = :c"), {"c": cuenta}
        ).scalar_one()


def clave_guardada(bd, cuenta: str, clave: UUID) -> tuple[str, int | None] | None:
    with bd() as sesion:
        fila = sesion.execute(
            text(
                "SELECT operacion, transaccion_id FROM claves_idempotencia "
                "WHERE cuenta_solicitante_id = :c AND clave = :k"
            ),
            {"c": cuenta, "k": clave},
        ).one_or_none()
    return None if fila is None else (fila.operacion, fila.transaccion_id)


def esperar_error(bd, codigo: str, operacion: Callable[[], object], bolsa_id=None):
    """Exige el `codigo` y que no cambie nada: ni transacciones, ni claves, ni
    estados de la bolsa (regla 4 del dinero).
    """
    antes = conteos(bd)
    estados_antes = estados(bd, bolsa_id) if bolsa_id else None
    bolsa_antes = estado_bolsa(bd, bolsa_id) if bolsa_id else None
    with pytest.raises(ErrorDominio) as exc:
        operacion()
    assert exc.value.codigo == codigo
    assert conteos(bd) == antes
    if bolsa_id:
        assert estados(bd, bolsa_id) == estados_antes
        assert estado_bolsa(bd, bolsa_id) == bolsa_antes


def resultado(operacion: Callable[[], object]) -> tuple[str, object]:
    """("ok", valor) o ("error", codigo): para las pruebas secuenciales."""
    try:
        return "ok", operacion()
    except ErrorDominio as error:
        return "error", error.codigo
