"""Filas del núcleo de la tabla 8.4, en orden fijo y sin hilos (SPEC 10.4).

Cada operación usa su propia sesión. Datos de partida exactos de la tabla.
"""

from uuid import uuid4

import pytest

from app.domain.errores import ClaveReutilizada, SaldoInsuficiente
from app.services.nucleo import cargar, transferir
from tests.services.apoyo_libro import AHORA, contar, saldo


def hacer_cargar(bd, token, monto, clave=None):
    with bd() as sesion:
        return cargar(sesion, token, clave or uuid4(), monto, AHORA)


def hacer_transferir(bd, token, destino, monto, clave=None):
    with bd() as sesion:
        return transferir(sesion, token, clave or uuid4(), destino, monto, AHORA)


# --- Dos transferencias que juntas superan el saldo -------------------------


@pytest.mark.parametrize("orden", ["a_luego_b", "b_luego_a"])
def test_dos_transferencias_que_superan_saldo(bd, ana, beto, orden):
    hacer_cargar(bd, ana, 100_000)
    clave_a, clave_b = uuid4(), uuid4()
    primera, segunda = (
        (clave_a, clave_b) if orden == "a_luego_b" else (clave_b, clave_a)
    )
    hacer_transferir(bd, ana, "beto", 60_000, primera)
    with pytest.raises(SaldoInsuficiente):
        hacer_transferir(bd, ana, "beto", 60_000, segunda)
    assert saldo(bd, "ana") == 40_000
    assert saldo(bd, "beto") == 60_000
    assert contar(bd, "transacciones") == 2  # la carga y una transferencia


# --- Transferencias cruzadas ------------------------------------------------


@pytest.mark.parametrize("orden", ["a_luego_b", "b_luego_a"])
def test_transferencias_cruzadas(bd, ana, beto, orden):
    hacer_cargar(bd, ana, 100_000)
    hacer_cargar(bd, beto, 100_000)
    if orden == "a_luego_b":
        hacer_transferir(bd, ana, "beto", 10_000)
        hacer_transferir(bd, beto, "ana", 10_000)
    else:
        hacer_transferir(bd, beto, "ana", 10_000)
        hacer_transferir(bd, ana, "beto", 10_000)
    assert saldo(bd, "ana") == 100_000
    assert saldo(bd, "beto") == 100_000
    assert contar(bd, "transacciones") == 4


# --- Misma clave y mismo cuerpo ---------------------------------------------


@pytest.mark.parametrize("orden", ["a_luego_b", "b_luego_a"])
def test_misma_clave_mismo_cuerpo(bd, ana, beto, orden):
    # Las dos peticiones son idénticas: el orden solo cambia cuál es "A".
    hacer_cargar(bd, ana, 100_000)
    clave = uuid4()
    primera = hacer_transferir(bd, ana, "beto", 10_000, clave)
    segunda = hacer_transferir(bd, ana, "beto", 10_000, clave)
    assert segunda == primera
    assert saldo(bd, "ana") == 90_000
    assert saldo(bd, "beto") == 10_000
    assert contar(bd, "transacciones") == 2
    assert contar(bd, "claves_idempotencia") == 2  # la carga y la transferencia


# --- Misma clave con otro cuerpo --------------------------------------------


@pytest.mark.parametrize(
    ("primero", "segundo"),
    [(10_000, 20_000), (20_000, 10_000)],
    ids=["a_luego_b", "b_luego_a"],
)
def test_misma_clave_otro_cuerpo(bd, ana, beto, primero, segundo):
    hacer_cargar(bd, ana, 100_000)
    clave = uuid4()
    respuesta = hacer_transferir(bd, ana, "beto", primero, clave)
    assert respuesta.monto == primero
    with pytest.raises(ClaveReutilizada):
        hacer_transferir(bd, ana, "beto", segundo, clave)
    assert saldo(bd, "ana") == 100_000 - primero
    assert saldo(bd, "beto") == primero
    assert contar(bd, "transacciones") == 2


# --- 100 cargas y 100 transferencias (un solo orden) ------------------------


def test_cien_cargas_secuenciales_todas_pasan(bd, ana):
    for _ in range(100):
        hacer_cargar(bd, ana, 1_000)
    assert saldo(bd, "ana") == 100_000
    assert saldo(bd, "sistema") == -100_000
    assert contar(bd, "transacciones") == 100


def test_cien_transferencias_secuenciales_cincuenta_y_cincuenta(bd, ana, beto):
    hacer_cargar(bd, ana, 1_000_000)
    pasan = rechazadas = 0
    for _ in range(100):
        try:
            hacer_transferir(bd, ana, "beto", 20_000)
            pasan += 1
        except SaldoInsuficiente:
            rechazadas += 1
    assert (pasan, rechazadas) == (50, 50)
    assert saldo(bd, "ana") == 0
    assert saldo(bd, "beto") == 1_000_000
