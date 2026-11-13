"""Consultas de solo lectura del núcleo: saldo e historial (SPEC 5.7 y 5.8).

Cada consulta corre en una transacción READ ONLY y no bloquea ninguna fila.
No usa el envoltorio de reintentos: una lectura sin bloqueos en READ
COMMITTED no produce 40P01 ni 40001.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domain.validaciones import validar_paginacion
from app.services.sesiones import autenticar

_SALDO = text("SELECT saldo FROM cuentas WHERE id = :cuenta")

# Consulta de SPEC 5.8. t.id solo desempata: no se selecciona.
_HISTORIAL = text(
    """
    SELECT t.tipo,
           CASE WHEN t.cuenta_origen_id = :cuenta THEN t.cuenta_destino_id
                ELSE t.cuenta_origen_id END AS contrapartida,
           m.monto,
           t.creado_en
    FROM movimientos m
    JOIN transacciones t ON t.id = m.transaccion_id
    WHERE m.cuenta_id = :cuenta
    ORDER BY t.creado_en DESC, t.id DESC
    LIMIT :cantidad OFFSET :desde
    """
)


@dataclass(frozen=True)
class SaldoCuenta:
    cuenta: str
    saldo: int


@dataclass(frozen=True)
class EntradaHistorial:
    """Una entrada del historial. Sin id de transacción ni saldo (SPEC 5.8)."""

    tipo: str
    contrapartida: str
    monto: int
    creado_en: datetime


def _solo_lectura(sesion: Session) -> None:
    """Primera sentencia de la transacción: la marca de solo lectura."""
    sesion.execute(text("SET TRANSACTION READ ONLY"))


def consultar_saldo(sesion: Session, token: str, ahora: datetime) -> SaldoCuenta:
    with sesion.begin():
        _solo_lectura(sesion)
        cuenta = autenticar(sesion, token, ahora).cuenta_id
        saldo = sesion.execute(_SALDO, {"cuenta": cuenta}).scalar_one()
    return SaldoCuenta(cuenta=cuenta, saldo=saldo)


def consultar_historial(
    sesion: Session, token: str, desde: int, cantidad: int, ahora: datetime
) -> list[EntradaHistorial]:
    with sesion.begin():
        _solo_lectura(sesion)
        cuenta = autenticar(sesion, token, ahora).cuenta_id
        validar_paginacion(desde, cantidad)
        filas = sesion.execute(
            _HISTORIAL, {"cuenta": cuenta, "desde": desde, "cantidad": cantidad}
        ).all()
    return [
        EntradaHistorial(f.tipo, f.contrapartida, f.monto, f.creado_en) for f in filas
    ]
