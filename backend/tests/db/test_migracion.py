"""La migración de T2 sube y baja de cero, y los modelos la reflejan."""

from collections.abc import Iterator

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Engine, create_engine, make_url, text
from sqlalchemy.pool import NullPool

from app.db.modelos import Base
from tests.bd_prueba import borrar_base, degradar, migrar, recrear_base

# Base aparte para no tocar cuadre_test, que comparten las demás pruebas.
BASE_MIGRACION = "cuadre_migracion_test"

TABLAS = {
    "cuentas",
    "usuarios",
    "sesiones",
    "transacciones",
    "movimientos",
    "claves_idempotencia",
    "bolsas",
    "participantes",
}


@pytest.fixture
def url_migracion(url_prueba: str) -> Iterator[str]:
    url = (
        make_url(url_prueba)
        .set(database=BASE_MIGRACION)
        .render_as_string(hide_password=False)
    )
    recrear_base(url)
    try:
        yield url
    finally:
        borrar_base(url)


def _consultar(url: str, sql: str) -> list[tuple]:
    motor = create_engine(url, poolclass=NullPool)
    try:
        with motor.connect() as conexion:
            return [tuple(f) for f in conexion.execute(text(sql)).all()]
    finally:
        motor.dispose()


def _tablas(url: str) -> set[str]:
    filas = _consultar(
        url, "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
    )
    return {tabla for (tabla,) in filas}


def test_migracion_crea_la_cuenta_de_sistema(url_migracion: str) -> None:
    migrar(url_migracion)
    filas = _consultar(url_migracion, "SELECT id, tipo, saldo FROM cuentas")
    assert filas == [("sistema", "sistema", 0)]


def test_downgrade_y_upgrade_de_cero(url_migracion: str) -> None:
    migrar(url_migracion)
    assert _tablas(url_migracion) == TABLAS | {"alembic_version"}

    degradar(url_migracion, "base")
    assert _tablas(url_migracion) == {"alembic_version"}

    migrar(url_migracion)
    assert _tablas(url_migracion) == TABLAS | {"alembic_version"}
    filas = _consultar(url_migracion, "SELECT id FROM cuentas")
    assert filas == [("sistema",)]


def test_modelos_coinciden_con_la_migracion(motor_prueba: Engine) -> None:
    with motor_prueba.connect() as conexion:
        diferencias = compare_metadata(
            MigrationContext.configure(conexion), Base.metadata
        )
    assert diferencias == []
