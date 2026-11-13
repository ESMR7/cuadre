"""Confirmar (SPEC 6.7 y 9.4, T11). Sin clave de idempotencia."""

from uuid import uuid4

import pytest

from app.services.operaciones_bolsa import ResultadoConfirmar
from tests.services.apoyo_bolsas import conteos
from tests.services.apoyo_operaciones_bolsa import (
    FECHA_CORTA,
    SALDO_INICIAL,
    Tx,
    esperar_error,
    estado_bolsa,
    estados,
    hacer_aportar,
    hacer_confirmar,
    hacer_retirarse,
    nueva_bolsa,
    saldo_de,
    sin_reintentos,  # noqa: F401
    transacciones,
    usuarios,
)

pytestmark = pytest.mark.usefixtures("sin_reintentos")


@pytest.fixture
def tokens(bd):
    return usuarios(bd, "ana", "beto", "carla", "dani", "olga")


@pytest.fixture
def bolsa_por_confirmar(bd, tokens):
    """Bolsa de $120.000: ana, beto y carla pagaron y dani se retiró, así que
    los tres quedan en por_confirmar (meta $90.000).
    """
    bolsa = nueva_bolsa(
        bd, tokens, participantes=("ana", "beto", "carla", "dani"), total=120_000
    )
    for n in ("ana", "beto", "carla"):
        hacer_aportar(bd, tokens[n], bolsa)
    hacer_retirarse(bd, tokens["dani"], bolsa)
    return bolsa


def test_confirmar_pasa_a_pagado_sin_mover_dinero(bd, tokens, bolsa_por_confirmar):
    antes = conteos(bd)
    r = hacer_confirmar(bd, tokens["ana"], bolsa_por_confirmar)
    assert r == ResultadoConfirmar(estado_bolsa="abierta", mi_estado="pagado")
    assert conteos(bd) == antes
    assert estados(bd, bolsa_por_confirmar)["ana"] == "pagado"


def test_ultima_confirmacion_transfiere_y_cierra(bd, tokens, bolsa_por_confirmar):
    hacer_confirmar(bd, tokens["ana"], bolsa_por_confirmar)
    hacer_confirmar(bd, tokens["beto"], bolsa_por_confirmar)
    r = hacer_confirmar(bd, tokens["carla"], bolsa_por_confirmar)
    assert r == ResultadoConfirmar(estado_bolsa="cerrada", mi_estado="pagado")
    assert transacciones(bd, "transferencia_final") == [
        Tx("transferencia_final", "bolsa-ana-cena", "olga", 90_000)
    ]
    assert saldo_de(bd, "bolsa-ana-cena") == 0
    assert saldo_de(bd, "olga") == SALDO_INICIAL + 90_000
    assert estado_bolsa(bd, bolsa_por_confirmar) == "cerrada"


def test_confirmacion_repetida_da_estado_invalido(bd, tokens, bolsa_por_confirmar):
    hacer_confirmar(bd, tokens["ana"], bolsa_por_confirmar)
    esperar_error(
        bd,
        "estado_invalido",
        lambda: hacer_confirmar(bd, tokens["ana"], bolsa_por_confirmar),
        bolsa_por_confirmar,
    )


def test_confirmar_pendiente_da_estado_invalido(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    esperar_error(
        bd, "estado_invalido", lambda: hacer_confirmar(bd, tokens["beto"], bolsa), bolsa
    )


def test_confirmar_retirado_da_estado_invalido(bd, tokens, bolsa_por_confirmar):
    esperar_error(
        bd,
        "estado_invalido",
        lambda: hacer_confirmar(bd, tokens["dani"], bolsa_por_confirmar),
        bolsa_por_confirmar,
    )


def test_confirmar_fuera_de_plazo(bd, tokens, bolsa_por_confirmar):
    esperar_error(
        bd,
        "fuera_de_plazo",
        lambda: hacer_confirmar(bd, tokens["ana"], bolsa_por_confirmar, FECHA_CORTA),
        bolsa_por_confirmar,
    )


def test_confirmar_no_participante_da_sin_permiso(bd, tokens, bolsa_por_confirmar):
    esperar_error(
        bd,
        "sin_permiso",
        lambda: hacer_confirmar(bd, tokens["olga"], bolsa_por_confirmar),
        bolsa_por_confirmar,
    )


def test_confirmar_bolsa_inexistente_da_no_encontrado(bd, tokens):
    esperar_error(
        bd, "no_encontrado", lambda: hacer_confirmar(bd, tokens["ana"], uuid4())
    )
