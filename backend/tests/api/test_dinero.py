"""POST /cargas y POST /transferencias (SPEC 5.4 a 5.6 y 9.3)."""

from uuid import uuid1, uuid4

import pytest

import app.api.dinero
from app.domain.constantes import TOPE_OPERACION
from app.domain.errores import ReintentosAgotados
from tests.api.conftest import cargar, con_clave, error


def test_cargar_devuelve_201_transaccion(cliente, ana):
    r = cliente.post("/cargas", json={"monto": 100000}, headers=con_clave(ana))
    assert r.status_code == 201
    cuerpo = r.json()
    assert isinstance(cuerpo["id"], int)
    del cuerpo["id"]
    assert cuerpo == {
        "tipo": "carga",
        "origen": "sistema",
        "destino": "ana",
        "monto": 100000,
        "creado_en": "2026-11-13T15:00:00Z",
    }


def test_transferir_devuelve_201_y_normaliza_destino(cliente, ana, beto):
    cargar(cliente, ana, 50000)
    r = cliente.post(
        "/transferencias",
        json={"destino": "BeTo", "monto": 20000},
        headers=con_clave(ana),
    )
    assert r.status_code == 201
    cuerpo = r.json()
    del cuerpo["id"]
    assert cuerpo == {
        "tipo": "transferencia",
        "origen": "ana",
        "destino": "beto",
        "monto": 20000,
        "creado_en": "2026-11-13T15:00:00Z",
    }
    assert cliente.get("/cuenta", headers=beto).json()["saldo"] == 20000


@pytest.mark.parametrize("monto", ["1000.0", "1e3", "true", '"1000"', "null", "[1000]"])
@pytest.mark.parametrize("ruta", ["/cargas", "/transferencias"])
def test_monto_no_entero_da_forma_invalida(cliente, ana, beto, monto, ruta):
    extra = '"destino": "beto", ' if ruta == "/transferencias" else ""
    r = cliente.post(
        ruta,
        content=f'{{{extra}"monto": {monto}}}',
        headers={**con_clave(ana), "Content-Type": "application/json"},
    )
    assert error(r, 422, "forma_invalida")["campos"] == ["monto"]


@pytest.mark.parametrize("monto", [0, -1])
def test_monto_cero_negativo_da_monto_invalido(cliente, ana, monto):
    r = cliente.post("/cargas", json={"monto": monto}, headers=con_clave(ana))
    error(r, 422, "monto_invalido")


def test_monto_sobre_el_tope_da_422(cliente, ana):
    r = cliente.post(
        "/cargas", json={"monto": TOPE_OPERACION + 1}, headers=con_clave(ana)
    )
    error(r, 422, "sobre_el_tope")


def test_transferencia_a_si_mismo_da_422(cliente, ana):
    cargar(cliente, ana, 1000)
    r = cliente.post(
        "/transferencias", json={"destino": "ANA", "monto": 1}, headers=con_clave(ana)
    )
    error(r, 422, "transferencia_a_si_mismo")


@pytest.mark.parametrize("destino", ["nadie", "sistema", "ana\n", ""])
def test_destino_inexistente_o_sistema_da_404(cliente, ana, destino):
    cargar(cliente, ana, 1000)
    r = cliente.post(
        "/transferencias", json={"destino": destino, "monto": 1}, headers=con_clave(ana)
    )
    error(r, 404, "no_encontrado")


def test_saldo_insuficiente_da_409(cliente, ana, beto):
    r = cliente.post(
        "/transferencias", json={"destino": "beto", "monto": 1}, headers=con_clave(ana)
    )
    error(r, 409, "saldo_insuficiente")


@pytest.mark.parametrize("ruta", ["/cargas", "/transferencias"])
def test_sin_clave_da_400(cliente, ana, ruta):
    r = cliente.post(ruta, json={"destino": "beto", "monto": 1}, headers=ana)
    error(r, 400, "falta_clave_idempotencia")


@pytest.mark.parametrize("clave", ["abc", "", str(uuid1()), str(uuid4()) + "\n"])
def test_clave_no_uuid_v4_da_422(cliente, ana, clave):
    r = cliente.post(
        "/cargas", json={"monto": 1}, headers={**ana, "Idempotency-Key": clave}
    )
    assert error(r, 422, "forma_invalida")["campos"] == ["Idempotency-Key"]


def test_reintento_misma_clave_mismo_codigo_y_cuerpo(cliente, ana, beto):
    cargar(cliente, ana, 50000)
    cabeceras = con_clave(ana)
    peticion = {"destino": "beto", "monto": 20000}
    primera = cliente.post("/transferencias", json=peticion, headers=cabeceras)
    segunda = cliente.post(
        "/transferencias", json={"destino": "BETO", "monto": 20000}, headers=cabeceras
    )
    assert primera.status_code == segunda.status_code == 201
    assert primera.content == segunda.content
    assert cliente.get("/cuenta", headers=ana).json()["saldo"] == 30000


def test_reintento_tras_nuevo_login_devuelve_lo_mismo(cliente, ana):
    from tests.api.conftest import entrar

    cabeceras = con_clave(ana)
    primera = cliente.post("/cargas", json={"monto": 7}, headers=cabeceras)
    nuevas = {**entrar(cliente, "ana"), "Idempotency-Key": cabeceras["Idempotency-Key"]}
    segunda = cliente.post("/cargas", json={"monto": 7}, headers=nuevas)
    assert primera.status_code == segunda.status_code == 201
    assert primera.content == segunda.content


def test_misma_clave_otro_cuerpo_da_409_clave_reutilizada(cliente, ana):
    cabeceras = con_clave(ana)
    assert (
        cliente.post("/cargas", json={"monto": 1}, headers=cabeceras).status_code == 201
    )
    r = cliente.post("/cargas", json={"monto": 2}, headers=cabeceras)
    error(r, 409, "clave_reutilizada")


def test_cuerpo_con_campo_desconocido_da_422(cliente, ana):
    r = cliente.post(
        "/cargas", json={"monto": 1, "destino": "x"}, headers=con_clave(ana)
    )
    assert error(r, 422, "forma_invalida")["campos"] == ["destino"]


def test_reintentos_agotados_da_503(cliente, ana, monkeypatch):
    def agotado(*args, **kwargs):
        raise ReintentosAgotados()

    monkeypatch.setattr(app.api.dinero, "cargar", agotado)
    r = cliente.post("/cargas", json={"monto": 1}, headers=con_clave(ana))
    error(r, 503, "reintentos_agotados")
