"""Ayudas para las pruebas del libro y del núcleo (T6)."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy import Engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.services.sesiones import iniciar_sesion
from app.services.usuarios import registrar

AHORA = datetime(2026, 11, 13, 15, 0, tzinfo=UTC)
CONTRASENA = "clave-segura-1"


def crear_usuario(bd: sessionmaker[Session], nombre: str, cedula: str) -> str:
    """Registra al usuario, inicia sesión y devuelve el token."""
    with bd() as sesion:
        registrar(sesion, nombre, cedula, CONTRASENA, AHORA)
    with bd() as sesion:
        return iniciar_sesion(sesion, nombre, CONTRASENA, AHORA).token


def saldo(bd: sessionmaker[Session], cuenta: str) -> int:
    with bd() as sesion:
        return sesion.execute(
            text("SELECT saldo FROM cuentas WHERE id = :id"), {"id": cuenta}
        ).scalar_one()


def contar(bd: sessionmaker[Session], tabla: str) -> int:
    assert tabla in {"transacciones", "movimientos", "claves_idempotencia"}
    with bd() as sesion:
        return sesion.execute(text(f"SELECT count(*) FROM {tabla}")).scalar_one()


@contextmanager
def capturar_sql(motor: Engine) -> Iterator[list[tuple[str, object]]]:
    """Guarda (sentencia, parámetros) de todo lo que se ejecuta en el motor."""
    sentencias: list[tuple[str, object]] = []

    def escuchar(conexion, cursor, sentencia, parametros, contexto, varias):
        sentencias.append((sentencia, parametros))

    event.listen(motor, "before_cursor_execute", escuchar)
    try:
        yield sentencias
    finally:
        event.remove(motor, "before_cursor_execute", escuchar)
