"""Reglas puras del libro (SPEC 3.5 y 3.9) y saldo suficiente."""

import pytest

from app.domain.errores import SaldoInsuficiente
from app.domain.libro import (
    TIPOS_PERMITIDOS,
    LibroDescuadrado,
    validar_tipos,
    verificar_patas,
)
from app.domain.validaciones import validar_saldo_suficiente


def test_tipos_permitidos_coinciden_con_tabla_3_5():
    assert TIPOS_PERMITIDOS == {
        "carga": ("sistema", "personal"),
        "transferencia": ("personal", "personal"),
        "aporte": ("personal", "bolsa"),
        "devolucion": ("bolsa", "personal"),
        "transferencia_final": ("bolsa", "personal"),
    }


@pytest.mark.parametrize(
    "tipo", ["carga", "transferencia", "aporte", "devolucion", "transferencia_final"]
)
def test_validar_tipos_acepta_la_combinacion_de_la_tabla(tipo):
    origen, destino = {
        "carga": ("sistema", "personal"),
        "transferencia": ("personal", "personal"),
        "aporte": ("personal", "bolsa"),
        "devolucion": ("bolsa", "personal"),
        "transferencia_final": ("bolsa", "personal"),
    }[tipo]
    validar_tipos(tipo, origen, destino)


@pytest.mark.parametrize(
    ("tipo", "origen", "destino"),
    [
        ("carga", "personal", "personal"),
        ("transferencia", "personal", "bolsa"),
        ("transferencia", "sistema", "personal"),
        ("aporte", "personal", "personal"),
        ("inventado", "personal", "personal"),
    ],
)
def test_validar_tipos_rechaza_combinacion_no_permitida(tipo, origen, destino):
    with pytest.raises(LibroDescuadrado):
        validar_tipos(tipo, origen, destino)


def test_verificar_patas_acepta_las_correctas():
    verificar_patas({"ana": -500, "beto": 500}, "ana", "beto", 500)


@pytest.mark.parametrize(
    "patas",
    [
        {"ana": -500, "beto": 400},  # suma distinta de cero
        {"ana": -500},  # falta una pata
        {"ana": -500, "beto": 500, "carla": 0},  # pata extra
        {"ana": -500, "carla": 500},  # cuenta cambiada
        {"ana": 500, "beto": -500},  # signos invertidos
        {"ana": -400, "beto": 400},  # monto distinto
    ],
)
def test_verificar_patas_rechaza_patas_incorrectas(patas):
    with pytest.raises(LibroDescuadrado):
        verificar_patas(patas, "ana", "beto", 500)


def test_validar_saldo_suficiente_acepta_igual_y_mayor():
    validar_saldo_suficiente(500, 500)
    validar_saldo_suficiente(501, 500)


def test_validar_saldo_suficiente_rechaza_menor():
    with pytest.raises(SaldoInsuficiente):
        validar_saldo_suficiente(499, 500)
