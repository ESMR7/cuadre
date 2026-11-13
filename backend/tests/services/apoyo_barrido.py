"""Ayudas para las pruebas del barrido (T14)."""

from datetime import datetime

from sqlalchemy import text

from app.services import barrido
from tests.services.apoyo_operaciones_bolsa import FECHA_CORTA


def correr_barrido(bd, ahora: datetime = FECHA_CORTA) -> barrido.ResumenBarrido:
    return barrido.procesar_vencidas(bd, ahora)


def hacer_preparar(bd, bolsa_id, ahora: datetime = FECHA_CORTA) -> bool:
    with bd() as sesion:
        return barrido.preparar(sesion, bolsa_id, ahora)


def hacer_devolver(bd, bolsa_id, cuenta: str, ahora: datetime = FECHA_CORTA):
    with bd() as sesion:
        return barrido.devolver(sesion, bolsa_id, cuenta, ahora)


def hacer_cerrar(bd, bolsa_id, ahora: datetime = FECHA_CORTA):
    with bd() as sesion:
        return barrido.cerrar(sesion, bolsa_id, ahora)


def verificar_devoluciones(bd) -> None:
    """Regla 7 del plan: por (bolsa, participante), a lo sumo una devolución y
    lo devuelto nunca supera lo aportado.
    """
    with bd() as sesion:
        filas = sesion.execute(
            text(
                """
                SELECT b.id, p.cuenta_id,
                       COUNT(*) FILTER (WHERE t.tipo = 'devolucion'
                                        AND t.cuenta_origen_id = b.cuenta_id
                                        AND t.cuenta_destino_id = p.cuenta_id)
                           AS n_dev,
                       COALESCE(SUM(t.monto) FILTER (
                           WHERE t.tipo = 'devolucion'
                             AND t.cuenta_origen_id = b.cuenta_id
                             AND t.cuenta_destino_id = p.cuenta_id), 0) AS dev,
                       COALESCE(SUM(t.monto) FILTER (
                           WHERE t.tipo = 'aporte'
                             AND t.cuenta_origen_id = p.cuenta_id
                             AND t.cuenta_destino_id = b.cuenta_id), 0) AS apo
                FROM participantes p
                JOIN bolsas b ON b.id = p.bolsa_id
                LEFT JOIN transacciones t ON TRUE
                GROUP BY b.id, p.cuenta_id
                """
            )
        ).all()
    for f in filas:
        assert f.n_dev <= 1, f"{f.cuenta_id} tiene {f.n_dev} devoluciones"
        assert f.dev <= f.apo, f"{f.cuenta_id}: devuelto {f.dev} > aportado {f.apo}"
