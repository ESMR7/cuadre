"""Fixtures comunes de las pruebas de concurrencia del núcleo (T7)."""

import pytest

from app.services.reintentos import reiniciar_contador, reintentos_por_codigo
from tests.services.apoyo_libro import crear_usuario


@pytest.fixture(autouse=True)
def sin_reintentos():
    """Cero reintentos de cualquier código (SPEC 10.4, punto 4)."""
    reiniciar_contador()
    yield
    assert reintentos_por_codigo() == {}


@pytest.fixture
def ana(bd) -> str:
    return crear_usuario(bd, "ana", "1000001")


@pytest.fixture
def beto(bd) -> str:
    return crear_usuario(bd, "beto", "1000002")
