"""POST /usuarios (SPEC 5.2 y 9.3)."""

import pytest

from tests.api.conftest import CONTRASENA, error


def cuerpo(**cambios):
    base = {"nombre_usuario": "ana", "cedula": "1000001", "contrasena": CONTRASENA}
    return {**base, **cambios}


def test_registro_devuelve_201_sin_cedula(cliente):
    r = cliente.post("/usuarios", json=cuerpo())
    assert r.status_code == 201
    assert r.json() == {"nombre_usuario": "ana", "creado_en": "2026-11-13T15:00:00Z"}
    assert "1000001" not in r.text


def test_registro_normaliza_a_minusculas(cliente):
    r = cliente.post("/usuarios", json=cuerpo(nombre_usuario="AnA_1"))
    assert r.status_code == 201
    assert r.json()["nombre_usuario"] == "ana_1"


def test_registro_rechaza_nombre_con_salto_de_linea_final(cliente):
    r = cliente.post("/usuarios", json=cuerpo(nombre_usuario="ana\n"))
    assert error(r, 422, "forma_invalida")["campos"] == ["nombre_usuario"]


@pytest.mark.parametrize(
    "nombre", ["ñandu", "a b", "ab", "a" * 31, "a-b", "Sistema", "anà", 123]
)
def test_registro_rechaza_nombres_invalidos(cliente, nombre):
    r = cliente.post("/usuarios", json=cuerpo(nombre_usuario=nombre))
    assert error(r, 422, "forma_invalida")["campos"] == ["nombre_usuario"]


@pytest.mark.parametrize("cedula", ["1234", "1" * 11, "12345\n", "12a45", 1234567])
def test_registro_rechaza_cedula_invalida(cliente, cedula):
    r = cliente.post("/usuarios", json=cuerpo(cedula=cedula))
    assert error(r, 422, "forma_invalida")["campos"] == ["cedula"]


@pytest.mark.parametrize(
    ("contrasena", "valida"),
    [
        ("a" * 7, False),
        ("a" * 8, True),
        ("a" * 128, True),
        ("a" * 129, False),
        ("ñ" * 64, True),  # 128 bytes
        ("ñ" * 65, False),  # 65 caracteres, 130 bytes
    ],
)
def test_contrasena_se_mide_en_bytes(cliente, contrasena, valida):
    r = cliente.post("/usuarios", json=cuerpo(contrasena=contrasena))
    if valida:
        assert r.status_code == 201, r.text
    else:
        assert error(r, 422, "forma_invalida")["campos"] == ["contrasena"]


def test_registro_repetido_da_409_registro_rechazado(cliente):
    assert cliente.post("/usuarios", json=cuerpo()).status_code == 201
    error(
        cliente.post("/usuarios", json=cuerpo(cedula="2000002")),
        409,
        "registro_rechazado",
    )
    error(
        cliente.post("/usuarios", json=cuerpo(nombre_usuario="otra")),
        409,
        "registro_rechazado",
    )


def test_registro_rechaza_campo_desconocido(cliente):
    r = cliente.post("/usuarios", json=cuerpo(admin=True))
    assert error(r, 422, "forma_invalida")["campos"] == ["admin"]


def test_registro_rechaza_campo_faltante(cliente):
    datos = cuerpo()
    del datos["cedula"]
    assert error(cliente.post("/usuarios", json=datos), 422, "forma_invalida")[
        "campos"
    ] == ["cedula"]
