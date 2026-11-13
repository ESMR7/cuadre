"""Retirarse (SPEC 6.6, 3.6, 2.5 y L7, T11)."""

from uuid import uuid4

import pytest

import app.services.operaciones_bolsa as operaciones
from app.services.operaciones_bolsa import BolsaInconsistente, ResultadoRetiro
from tests.services.apoyo_bolsas import conteos
from tests.services.apoyo_operaciones_bolsa import (
    FECHA_CORTA,
    SALDO_INICIAL,
    Tx,
    clave_guardada,
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
    return usuarios(bd, "ana", "beto", "carla", "olga")


def test_retiro_sin_pago_devuelve_none_y_guarda_clave_sin_transaccion(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    clave = uuid4()
    r = hacer_retirarse(bd, tokens["beto"], bolsa, clave)
    assert r == ResultadoRetiro(devolucion=None)
    assert [t for t in transacciones(bd) if t.tipo != "carga"] == []
    assert clave_guardada(bd, "beto", clave) == ("retirarse", None)
    assert estados(bd, bolsa)["beto"] == "retirado"


def test_retiro_con_pago_devuelve_la_deuda_del_libro(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    hacer_aportar(bd, tokens["beto"], bolsa)
    clave = uuid4()
    r = hacer_retirarse(bd, tokens["beto"], bolsa, clave)
    d = r.devolucion
    assert (d.tipo, d.origen, d.destino, d.monto) == (
        "devolucion",
        "bolsa-ana-cena",
        "beto",
        30_000,
    )
    assert saldo_de(bd, "beto") == SALDO_INICIAL
    assert saldo_de(bd, "bolsa-ana-cena") == 0
    assert clave_guardada(bd, "beto", clave) == ("retirarse", d.id)


def test_retiro_pasa_todos_los_pagados_a_por_confirmar(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    hacer_aportar(bd, tokens["ana"], bolsa)
    hacer_aportar(bd, tokens["beto"], bolsa)
    hacer_retirarse(bd, tokens["carla"], bolsa)  # carla no había pagado
    assert estados(bd, bolsa) == {
        "ana": "por_confirmar",
        "beto": "por_confirmar",
        "carla": "retirado",
    }


def test_retiro_nunca_completa_la_bolsa(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    hacer_aportar(bd, tokens["ana"], bolsa)
    hacer_aportar(bd, tokens["beto"], bolsa)
    hacer_retirarse(bd, tokens["carla"], bolsa)
    assert estado_bolsa(bd, bolsa) == "abierta"
    assert transacciones(bd, "transferencia_final") == []
    assert saldo_de(bd, "bolsa-ana-cena") == 60_000


def test_ultimo_activo_sin_pago_cierra_en_cero(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens, participantes=("ana", "beto"), total=60_000)
    hacer_retirarse(bd, tokens["beto"], bolsa)
    hacer_retirarse(bd, tokens["ana"], bolsa)
    assert estado_bolsa(bd, bolsa) == "cerrada"
    assert saldo_de(bd, "bolsa-ana-cena") == 0


def test_ultimo_activo_pagado_recibe_devolucion_y_cierra_en_cero(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens, participantes=("ana", "beto"), total=60_000)
    hacer_aportar(bd, tokens["ana"], bolsa)
    hacer_retirarse(bd, tokens["beto"], bolsa)
    r = hacer_retirarse(bd, tokens["ana"], bolsa)
    assert r.devolucion.monto == 30_000
    assert estado_bolsa(bd, bolsa) == "cerrada"
    assert saldo_de(bd, "bolsa-ana-cena") == 0
    assert saldo_de(bd, "ana") == SALDO_INICIAL
    assert transacciones(bd, "transferencia_final") == []


def test_retiro_de_por_confirmar_devuelve_su_aporte(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    hacer_aportar(bd, tokens["ana"], bolsa)
    hacer_retirarse(bd, tokens["carla"], bolsa)  # ana pasa a por_confirmar
    r = hacer_retirarse(bd, tokens["ana"], bolsa)
    assert r.devolucion.monto == 30_000


def test_deuda_no_cuenta_la_transferencia_final_al_participante(bd, tokens):
    """Con objetivo ana, la transferencia final no es una devolución (3.6)."""
    bolsa = nueva_bolsa(bd, tokens, cuenta_objetivo="ana")
    for n in ("ana", "beto", "carla"):
        hacer_aportar(bd, tokens[n], bolsa)
    assert transacciones(bd, "devolucion") == []
    assert transacciones(bd, "transferencia_final") == [
        Tx("transferencia_final", "bolsa-ana-cena", "ana", 90_000)
    ]


# --- Idempotencia --------------------------------------------------------


def test_misma_clave_sin_pago_devuelve_none(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    clave = uuid4()
    hacer_retirarse(bd, tokens["beto"], bolsa, clave)
    antes = conteos(bd)
    assert hacer_retirarse(bd, tokens["beto"], bolsa, clave) == ResultadoRetiro(None)
    assert conteos(bd) == antes


def test_misma_clave_con_pago_devuelve_la_misma_devolucion(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    hacer_aportar(bd, tokens["beto"], bolsa)
    clave = uuid4()
    original = hacer_retirarse(bd, tokens["beto"], bolsa, clave)
    antes = conteos(bd)
    assert hacer_retirarse(bd, tokens["beto"], bolsa, clave) == original
    assert conteos(bd) == antes


def test_misma_clave_en_otra_bolsa_da_clave_reutilizada(bd, tokens):
    una = nueva_bolsa(bd, tokens, nombre="una")
    otra = nueva_bolsa(bd, tokens, nombre="otra")
    clave = uuid4()
    hacer_retirarse(bd, tokens["beto"], una, clave)
    esperar_error(
        bd,
        "clave_reutilizada",
        lambda: hacer_retirarse(bd, tokens["beto"], otra, clave),
        otra,
    )


# --- Errores -------------------------------------------------------------


def test_retiro_repetido_da_estado_invalido(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    hacer_retirarse(bd, tokens["beto"], bolsa)
    esperar_error(
        bd, "estado_invalido", lambda: hacer_retirarse(bd, tokens["beto"], bolsa), bolsa
    )


def test_retiro_en_bolsa_cerrada_da_estado_invalido(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    for n in ("ana", "beto", "carla"):
        hacer_aportar(bd, tokens[n], bolsa)
    esperar_error(
        bd, "estado_invalido", lambda: hacer_retirarse(bd, tokens["beto"], bolsa), bolsa
    )


def test_retiro_fuera_de_plazo(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    hacer_aportar(bd, tokens["beto"], bolsa)
    esperar_error(
        bd,
        "fuera_de_plazo",
        lambda: hacer_retirarse(bd, tokens["beto"], bolsa, ahora=FECHA_CORTA),
        bolsa,
    )


def test_retiro_no_participante_da_sin_permiso(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    esperar_error(
        bd, "sin_permiso", lambda: hacer_retirarse(bd, tokens["olga"], bolsa), bolsa
    )


def test_retiro_bolsa_inexistente_da_no_encontrado(bd, tokens):
    esperar_error(
        bd, "no_encontrado", lambda: hacer_retirarse(bd, tokens["ana"], uuid4())
    )


# --- Descuadre (opción a: se reemplaza un paso del servicio) -------------


def test_deuda_distinta_de_la_parte_revierte_todo(bd, tokens, monkeypatch):
    """Si la deuda del libro no es la parte: BolsaInconsistente y nada cambia.

    Último activo pagado: si la devolución se hiciera por menos, la bolsa
    quedaría con saldo y el cierre en cero también la rechazaría.
    """
    bolsa = nueva_bolsa(bd, tokens, participantes=("ana", "beto"), total=60_000)
    hacer_aportar(bd, tokens["ana"], bolsa)
    hacer_retirarse(bd, tokens["beto"], bolsa)
    real = operaciones.deuda_participante
    monkeypatch.setattr(
        operaciones,
        "deuda_participante",
        lambda sesion, cuenta_bolsa, cuenta: real(sesion, cuenta_bolsa, cuenta) - 1,
    )
    antes = conteos(bd)
    estados_antes = estados(bd, bolsa)
    clave = uuid4()
    with pytest.raises(BolsaInconsistente):
        hacer_retirarse(bd, tokens["ana"], bolsa, clave)
    assert conteos(bd) == antes
    assert estados(bd, bolsa) == estados_antes
    assert estado_bolsa(bd, bolsa) == "abierta"
    assert clave_guardada(bd, "ana", clave) is None
    assert saldo_de(bd, "bolsa-ana-cena") == 30_000


def test_confirmar_tras_retiro_sigue_funcionando(bd, tokens):
    """Retiro deja por_confirmar; confirmar lo devuelve a pagado (6.6 y 6.7)."""
    bolsa = nueva_bolsa(bd, tokens)
    hacer_aportar(bd, tokens["ana"], bolsa)
    hacer_retirarse(bd, tokens["carla"], bolsa)
    hacer_confirmar(bd, tokens["ana"], bolsa)
    assert estados(bd, bolsa)["ana"] == "pagado"
