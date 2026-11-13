"""Cliente HTTP contra cuadre_test con hora fija (SPEC 10.2).

`obtener_sesion_bd` usa la fábrica del fixture `bd` y `obtener_ahora` lee
`reloj.ahora`, que una prueba puede mover para vencer un token.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencias import obtener_ahora, obtener_sesion_bd
from app.main import app
from tests.services.apoyo_libro import AHORA

CONTRASENA = "contrasena-segura"


@dataclass
class Reloj:
    ahora: datetime


@pytest.fixture
def reloj() -> Reloj:
    return Reloj(AHORA)


@pytest.fixture
def cliente(bd: sessionmaker[Session], reloj: Reloj) -> Iterator[TestClient]:
    def sesion_de_prueba() -> Iterator[Session]:
        with bd() as sesion:
            yield sesion

    app.dependency_overrides[obtener_sesion_bd] = sesion_de_prueba
    app.dependency_overrides[obtener_ahora] = lambda: reloj.ahora
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        app.dependency_overrides.clear()


def registrar(cliente: TestClient, nombre: str, cedula: str) -> None:
    r = cliente.post(
        "/usuarios",
        json={"nombre_usuario": nombre, "cedula": cedula, "contrasena": CONTRASENA},
    )
    assert r.status_code == 201, r.text


def entrar(cliente: TestClient, nombre: str) -> dict[str, str]:
    r = cliente.post(
        "/sesiones", json={"nombre_usuario": nombre, "contrasena": CONTRASENA}
    )
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def con_clave(cabeceras: dict[str, str], clave: str | None = None) -> dict[str, str]:
    return {**cabeceras, "Idempotency-Key": clave or str(uuid4())}


@pytest.fixture
def ana(cliente: TestClient) -> dict[str, str]:
    registrar(cliente, "ana", "1000001")
    return entrar(cliente, "ana")


@pytest.fixture
def beto(cliente: TestClient) -> dict[str, str]:
    registrar(cliente, "beto", "1000002")
    return entrar(cliente, "beto")


def cargar(cliente: TestClient, cabeceras: dict[str, str], monto: int) -> None:
    r = cliente.post("/cargas", json={"monto": monto}, headers=con_clave(cabeceras))
    assert r.status_code == 201, r.text


def error(respuesta, http: int, codigo: str) -> dict:
    assert respuesta.status_code == http, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["codigo"] == codigo
    assert isinstance(cuerpo["mensaje"], str) and cuerpo["mensaje"]
    esperadas = {"codigo", "mensaje"} | (
        {"campos"} if codigo == "forma_invalida" else set()
    )
    assert set(cuerpo) == esperadas
    return cuerpo
