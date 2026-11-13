"""Inserciones con SQL directo para probar el esquema (T2).

Cada función inserta una fila válida; el llamador cambia solo el valor que
quiere probar. Las pruebas nunca confirman: la sesión se revierte al salir,
así no quedan en el libro transacciones sin movimientos.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from sqlalchemy import CursorResult, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

AHORA = datetime(2026, 11, 13, 15, 0, tzinfo=UTC)
HASH_VALIDO = "a" * 64

# Códigos SQLSTATE de PostgreSQL.
CHECK = "23514"
UNICA = "23505"
FORANEA = "23503"
NO_NULA = "23502"
GENERADA_SIEMPRE = "428C9"


def ejecutar(sesion: Session, sql: str, **parametros: Any) -> CursorResult[Any]:
    return sesion.execute(text(sql), parametros)


def insertar_cuenta(
    sesion: Session, id: str, tipo: str = "personal", saldo: int = 0
) -> str:
    ejecutar(
        sesion,
        "INSERT INTO cuentas (id, tipo, saldo, creada_en) "
        "VALUES (:id, :tipo, :saldo, :ahora)",
        id=id,
        tipo=tipo,
        saldo=saldo,
        ahora=AHORA,
    )
    return id


def insertar_usuario(
    sesion: Session, nombre: str, cedula: str, cuenta_id: str | None = None
) -> int:
    return ejecutar(
        sesion,
        "INSERT INTO usuarios (cedula, nombre_usuario, contrasena_hash, "
        "cuenta_id, creado_en) "
        "VALUES (:cedula, :nombre, 'scrypt$hash', :cuenta_id, :ahora) RETURNING id",
        cedula=cedula,
        nombre=nombre,
        cuenta_id=nombre if cuenta_id is None else cuenta_id,
        ahora=AHORA,
    ).scalar_one()


def crear_persona(sesion: Session, nombre: str, cedula: str) -> int:
    """Cuenta personal y usuario, en ese orden."""
    insertar_cuenta(sesion, nombre)
    return insertar_usuario(sesion, nombre, cedula)


def insertar_sesion(
    sesion: Session,
    usuario_id: int,
    token_hash: str = HASH_VALIDO,
    creada_en: datetime = AHORA,
    expira_en: datetime = AHORA + timedelta(minutes=20),
) -> None:
    ejecutar(
        sesion,
        "INSERT INTO sesiones (usuario_id, token_hash, creada_en, expira_en) "
        "VALUES (:usuario_id, :token_hash, :creada_en, :expira_en)",
        usuario_id=usuario_id,
        token_hash=token_hash,
        creada_en=creada_en,
        expira_en=expira_en,
    )


def insertar_transaccion(
    sesion: Session, tipo: str, origen: str, destino: str, monto: int = 1000
) -> int:
    return ejecutar(
        sesion,
        "INSERT INTO transacciones (tipo, cuenta_origen_id, cuenta_destino_id, "
        "monto, creado_en) VALUES (:tipo, :origen, :destino, :monto, :ahora) "
        "RETURNING id",
        tipo=tipo,
        origen=origen,
        destino=destino,
        monto=monto,
        ahora=AHORA,
    ).scalar_one()


def insertar_movimiento(
    sesion: Session, transaccion_id: int, cuenta_id: str, monto: int
) -> None:
    ejecutar(
        sesion,
        "INSERT INTO movimientos (transaccion_id, cuenta_id, monto) "
        "VALUES (:transaccion_id, :cuenta_id, :monto)",
        transaccion_id=transaccion_id,
        cuenta_id=cuenta_id,
        monto=monto,
    )


def insertar_clave(
    sesion: Session,
    solicitante: str,
    clave: UUID | None = None,
    operacion: str = "cargar",
    hash_peticion: str = HASH_VALIDO,
    transaccion_id: int | None = None,
) -> UUID:
    clave = uuid4() if clave is None else clave
    ejecutar(
        sesion,
        "INSERT INTO claves_idempotencia (cuenta_solicitante_id, clave, operacion, "
        "hash_peticion, transaccion_id, creado_en) "
        "VALUES (:solicitante, :clave, :operacion, :hash, :transaccion_id, :ahora)",
        solicitante=solicitante,
        clave=clave,
        operacion=operacion,
        hash=hash_peticion,
        transaccion_id=transaccion_id,
        ahora=AHORA,
    )
    return clave


def cuenta_de_bolsa(creador: str, nombre: str) -> str:
    return f"bolsa-{creador}-{nombre}"


def insertar_bolsa(
    sesion: Session,
    creador: str,
    nombre: str = "viaje",
    objetivo: str | None = None,
    *,
    id: UUID | None = None,
    total: int = 10000,
    cuenta_id: str | None = None,
    estado: str = "abierta",
    creada_en: datetime = AHORA,
    fecha_limite: datetime = AHORA + timedelta(days=7),
    transferir_al_vencer: bool = True,
) -> UUID:
    """Inserta solo la fila de la bolsa; su cuenta la crea `crear_bolsa`."""
    return ejecutar(
        sesion,
        "INSERT INTO bolsas (id, nombre, total, cuenta_id, creador_cuenta_id, "
        "cuenta_objetivo_id, transferir_al_vencer, fecha_limite, estado, "
        "creada_en) VALUES (COALESCE(:id, gen_random_uuid()), :nombre, :total, "
        ":cuenta_id, :creador, :objetivo, :transferir, :fecha_limite, :estado, "
        ":creada_en) RETURNING id",
        id=id,
        nombre=nombre,
        total=total,
        cuenta_id=cuenta_de_bolsa(creador, nombre) if cuenta_id is None else cuenta_id,
        creador=creador,
        objetivo=creador if objetivo is None else objetivo,
        transferir=transferir_al_vencer,
        fecha_limite=fecha_limite,
        estado=estado,
        creada_en=creada_en,
    ).scalar_one()


def crear_bolsa(
    sesion: Session, creador: str, nombre: str = "viaje", **opciones: Any
) -> UUID:
    """Cuenta de tipo bolsa y fila de la bolsa, en ese orden."""
    insertar_cuenta(sesion, cuenta_de_bolsa(creador, nombre), tipo="bolsa")
    return insertar_bolsa(sesion, creador, nombre, **opciones)


def insertar_participante(
    sesion: Session,
    bolsa_id: UUID,
    cuenta_id: str,
    parte: int = 5000,
    estado: str = "pendiente",
) -> None:
    ejecutar(
        sesion,
        "INSERT INTO participantes (bolsa_id, cuenta_id, parte, estado) "
        "VALUES (:bolsa_id, :cuenta_id, :parte, :estado)",
        bolsa_id=bolsa_id,
        cuenta_id=cuenta_id,
        parte=parte,
        estado=estado,
    )


def violar(accion: Callable[[], object]) -> psycopg.Error:
    """Ejecuta la acción, exige que PostgreSQL la rechace y devuelve el error."""
    with pytest.raises(DBAPIError) as error:
        accion()
    return error.value.orig


def esperar_violacion(
    accion: Callable[[], object], restriccion: str, sqlstate: str
) -> None:
    """La acción viola exactamente la restricción indicada, no otra."""
    error = violar(accion)
    assert error.sqlstate == sqlstate
    assert error.diag.constraint_name == restriccion
