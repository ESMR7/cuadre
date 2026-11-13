"""GET /cuenta y GET /cuenta/movimientos (SPEC 5.7, 5.8 y 9.3)."""

import pytest

from tests.api.conftest import cargar, con_clave, error


def test_saldo_devuelve_cuenta_y_saldo(cliente, ana):
    cargar(cliente, ana, 150000)
    r = cliente.get("/cuenta", headers=ana)
    assert r.status_code == 200
    assert r.json() == {"cuenta": "ana", "saldo": 150000}


def test_historial_formato_exacto_sin_id_ni_saldo(cliente, ana, beto):
    cargar(cliente, ana, 100000)
    r = cliente.post(
        "/transferencias",
        json={"destino": "beto", "monto": 20000},
        headers=con_clave(ana),
    )
    assert r.status_code == 201
    r = cliente.get("/cuenta/movimientos", headers=ana)
    assert r.status_code == 200
    assert r.json() == {
        "movimientos": [
            {
                "tipo": "transferencia",
                "contrapartida": "beto",
                "monto": -20000,
                "creado_en": "2026-11-13T15:00:00Z",
            },
            {
                "tipo": "carga",
                "contrapartida": "sistema",
                "monto": 100000,
                "creado_en": "2026-11-13T15:00:00Z",
            },
        ],
        "desde": 0,
        "cantidad": 20,
    }


def test_historial_paginacion_por_defecto_20(cliente, ana):
    for _ in range(21):
        cargar(cliente, ana, 1)
    r = cliente.get("/cuenta/movimientos", headers=ana)
    assert len(r.json()["movimientos"]) == 20
    r = cliente.get("/cuenta/movimientos?desde=20&cantidad=100", headers=ana)
    assert r.json()["desde"] == 20 and r.json()["cantidad"] == 100
    assert len(r.json()["movimientos"]) == 1


@pytest.mark.parametrize(
    ("consulta", "campo"),
    [
        ("desde=-1", "desde"),
        ("cantidad=0", "cantidad"),
        ("cantidad=101", "cantidad"),
        ("cantidad=x", "cantidad"),
        ("desde=1.5", "desde"),
    ],
)
def test_historial_paginacion_fuera_de_rango_da_422(cliente, ana, consulta, campo):
    r = cliente.get(f"/cuenta/movimientos?{consulta}", headers=ana)
    assert error(r, 422, "forma_invalida")["campos"] == [campo]
