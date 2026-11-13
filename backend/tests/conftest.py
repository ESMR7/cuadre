"""Fixtures de la base de pruebas (SPEC 10.2).

No son autouse: la base solo se crea si alguna prueba la pide, así las
pruebas puras de domain/ corren sin PostgreSQL.
"""

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import exigir
from app.db.sesion import crear_fabrica, crear_motor
from tests.bd_prueba import (
    DESBORDE_PRUEBAS,
    POOL_PRUEBAS,
    borrar_base,
    crear_cuenta_sistema,
    exigir_base_de_prueba,
    migrar,
    recrear_base,
    vaciar_tablas,
)


@pytest.fixture(scope="session")
def url_prueba() -> str:
    url = exigir("TEST_DATABASE_URL")
    exigir_base_de_prueba(url)
    return url


@pytest.fixture(scope="session")
def motor_prueba(url_prueba: str) -> Iterator[Engine]:
    """Crea cuadre_test de cero, la migra a head y la borra al terminar."""
    recrear_base(url_prueba)
    migrar(url_prueba)
    motor = crear_motor(
        url_prueba, pool_size=POOL_PRUEBAS, max_overflow=DESBORDE_PRUEBAS
    )
    try:
        yield motor
    finally:
        motor.dispose()
        borrar_base(url_prueba)


@pytest.fixture(scope="session")
def fabrica_sesiones(motor_prueba: Engine) -> sessionmaker[Session]:
    return crear_fabrica(motor_prueba)


@pytest.fixture
def bd(
    motor_prueba: Engine, fabrica_sesiones: sessionmaker[Session]
) -> Iterator[sessionmaker[Session]]:
    """Entrega la fábrica de sesiones y deja la base vacía al terminar.

    La cuenta de sistema se asegura también al empezar: una prueba que vacía
    las tablas sin este fixture (test_vaciar_tablas_deja_tablas_vacias) la
    borraría para la siguiente.
    """
    crear_cuenta_sistema(motor_prueba)
    yield fabrica_sesiones
    # T3: correr aquí todas las invariantes, antes de vaciar.
    vaciar_tablas(motor_prueba)
    crear_cuenta_sistema(motor_prueba)
