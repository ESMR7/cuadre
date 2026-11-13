"""Servicio del libro contable: único escritor de transacciones, movimientos
y saldos (reglas del dinero 2 y 3).

Las funciones corren dentro de la transacción que abre el caso de uso; no
hacen commit.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import insert, select, text, update
from sqlalchemy.orm import Session

from app.db.modelos import Cuenta, Movimiento, Transaccion
from app.domain.errores import NoEncontrado
from app.domain.libro import validar_tipos, verificar_patas


@dataclass(frozen=True)
class TransaccionRegistrada:
    id: int
    tipo: str
    origen: str
    destino: str
    monto: int
    creado_en: datetime


def bloquear_cuentas(
    sesion: Session, tipos_esperados: dict[str, str]
) -> dict[str, Cuenta]:
    """Bloquea cada cuenta con FOR NO KEY UPDATE, una sentencia por id, en orden
    ascendente y sin repetidos. Una cuenta que no existe con ese tipo: NoEncontrado.

    sorted() de Python coincide con COLLATE "C" porque los ids son ASCII.
    populate_existing refresca un objeto que ya estaba en la sesión: sin él,
    la fila quedaría bloqueada pero el saldo leído sería el viejo.
    """
    bloqueadas: dict[str, Cuenta] = {}
    for cuenta_id in sorted(tipos_esperados):
        cuenta = sesion.execute(
            select(Cuenta)
            .where(Cuenta.id == cuenta_id, Cuenta.tipo == tipos_esperados[cuenta_id])
            .with_for_update(key_share=True)
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()
        if cuenta is None:
            raise NoEncontrado()
        bloqueadas[cuenta_id] = cuenta
    return bloqueadas


def registrar_transaccion(
    sesion: Session,
    tipo: str,
    origen: Cuenta,
    destino: Cuenta,
    monto: int,
    ahora: datetime,
) -> TransaccionRegistrada:
    """Escribe una transacción en partida doble sobre cuentas ya bloqueadas.

    Cabecera, dos movimientos y dos saldos relativos (saldo = saldo + delta,
    calculado por PostgreSQL). Antes de volver relee las patas y verifica que
    cuadren; si no, LibroDescuadrado y el caso de uso revierte.
    """
    validar_tipos(tipo, origen.tipo, destino.tipo)
    transaccion_id = sesion.execute(
        insert(Transaccion)
        .values(
            tipo=tipo,
            cuenta_origen_id=origen.id,
            cuenta_destino_id=destino.id,
            monto=monto,
            creado_en=ahora,
        )
        .returning(Transaccion.id)
    ).scalar_one()
    for cuenta_id, delta in ((origen.id, -monto), (destino.id, monto)):
        sesion.execute(
            insert(Movimiento).values(
                transaccion_id=transaccion_id, cuenta_id=cuenta_id, monto=delta
            )
        )
        sesion.execute(
            update(Cuenta)
            .where(Cuenta.id == cuenta_id)
            .values(saldo=Cuenta.saldo + delta)
        )
    patas = {
        fila.cuenta_id: fila.monto
        for fila in sesion.execute(
            select(Movimiento.cuenta_id, Movimiento.monto).where(
                Movimiento.transaccion_id == transaccion_id
            )
        )
    }
    verificar_patas(patas, origen.id, destino.id, monto)
    return TransaccionRegistrada(
        id=transaccion_id,
        tipo=tipo,
        origen=origen.id,
        destino=destino.id,
        monto=monto,
        creado_en=ahora,
    )


def leer_transaccion(sesion: Session, transaccion_id: int) -> TransaccionRegistrada:
    fila = sesion.execute(
        select(Transaccion).where(Transaccion.id == transaccion_id)
    ).scalar_one()
    return TransaccionRegistrada(
        id=fila.id,
        tipo=fila.tipo,
        origen=fila.cuenta_origen_id,
        destino=fila.cuenta_destino_id,
        monto=fila.monto,
        creado_en=fila.creado_en,
    )


def deuda_participante(
    sesion: Session, cuenta_bolsa: str, cuenta_participante: str
) -> int:
    """Aportes menos devoluciones entre el participante y la bolsa (SPEC 3.6).

    Se calcula desde el libro y por tipo: una transferencia final hacia un
    participante nunca cuenta como devolución. Solo lee.
    """
    return sesion.execute(
        text(
            """
            SELECT COALESCE(SUM(CASE
                       WHEN tipo = 'aporte' AND cuenta_origen_id = :participante
                            AND cuenta_destino_id = :bolsa THEN monto
                       WHEN tipo = 'devolucion' AND cuenta_origen_id = :bolsa
                            AND cuenta_destino_id = :participante THEN -monto
                       ELSE 0 END), 0)
            FROM transacciones
            WHERE tipo IN ('aporte', 'devolucion')
              AND (cuenta_origen_id = :bolsa OR cuenta_destino_id = :bolsa)
            """
        ),
        {"bolsa": cuenta_bolsa, "participante": cuenta_participante},
    ).scalar_one()
