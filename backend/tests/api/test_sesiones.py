"""POST /sesiones, /sesiones/renovar y DELETE /sesiones (SPEC 5.3 y 9.3)."""

from datetime import timedelta

import pytest

from tests.api.conftest import CONTRASENA, error, registrar


def test_login_devuelve_201_token_y_expira_en(cliente):
    registrar(cliente, "ana", "1000001")
    r = cliente.post(
        "/sesiones", json={"nombre_usuario": "ana", "contrasena": CONTRASENA}
    )
    assert r.status_code == 201
    assert set(r.json()) == {"token", "expira_en"}
    assert r.json()["expira_en"] == "2026-11-13T15:20:00Z"


def test_login_normaliza_nombre(cliente):
    registrar(cliente, "ana", "1000001")
    r = cliente.post(
        "/sesiones", json={"nombre_usuario": "ANA", "contrasena": CONTRASENA}
    )
    assert r.status_code == 201


def test_login_invalido_da_401_mismo_mensaje(cliente):
    registrar(cliente, "ana", "1000001")
    a = cliente.post(
        "/sesiones", json={"nombre_usuario": "nadie", "contrasena": CONTRASENA}
    )
    b = cliente.post(
        "/sesiones", json={"nombre_usuario": "ana", "contrasena": "otra-clave"}
    )
    assert error(a, 401, "no_autenticado") == error(b, 401, "no_autenticado")


@pytest.mark.parametrize("contrasena", ["a" * 7, "a" * 129, "ñ" * 65])
def test_login_con_contrasena_fuera_de_rango_da_422(cliente, contrasena):
    r = cliente.post(
        "/sesiones", json={"nombre_usuario": "ana", "contrasena": contrasena}
    )
    assert error(r, 422, "forma_invalida")["campos"] == ["contrasena"]


def test_renovar_devuelve_200(cliente, ana, reloj):
    reloj.ahora += timedelta(minutes=15)
    r = cliente.post("/sesiones/renovar", headers=ana)
    assert r.status_code == 200
    assert r.json() == {"expira_en": "2026-11-13T15:35:00Z"}


def test_renovar_ignora_cuerpo(cliente, ana):
    r = cliente.post("/sesiones/renovar", headers=ana, json={"lo_que_sea": 1})
    assert r.status_code == 200


def test_logout_devuelve_204_y_token_deja_de_valer(cliente, ana):
    r = cliente.delete("/sesiones", headers=ana)
    assert r.status_code == 204
    assert r.content == b""
    error(cliente.get("/cuenta", headers=ana), 401, "no_autenticado")


@pytest.mark.parametrize(
    "authorization",
    [None, "Basic abc", "Bearer", "Bearer ", "Bearer a b", "Bearer tokenfalso", "abc"],
)
@pytest.mark.parametrize(
    ("metodo", "ruta"),
    [
        ("GET", "/cuenta"),
        ("GET", "/cuenta/movimientos"),
        ("POST", "/sesiones/renovar"),
        ("DELETE", "/sesiones"),
    ],
)
def test_authorization_ausente_mal_formada_o_invalida_da_401(
    cliente, ana, authorization, metodo, ruta
):
    cabeceras = {} if authorization is None else {"Authorization": authorization}
    error(cliente.request(metodo, ruta, headers=cabeceras), 401, "no_autenticado")


def test_token_expirado_da_401(cliente, ana, reloj):
    reloj.ahora += timedelta(minutes=20)
    error(cliente.get("/cuenta", headers=ana), 401, "no_autenticado")
    error(cliente.post("/sesiones/renovar", headers=ana), 401, "no_autenticado")


def test_bearer_sin_distinguir_mayusculas(cliente, ana):
    token = ana["Authorization"].split(" ")[1]
    r = cliente.get("/cuenta", headers={"Authorization": f"bearer {token}"})
    assert r.status_code == 200
