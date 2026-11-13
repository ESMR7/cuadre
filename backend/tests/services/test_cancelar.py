"""Cancelar (SPEC 7.1 con el recorte 2, 8.2; T13).

Recorte 2 (DECISIONS.md, 2026-11-13): cancelar siempre devuelve todo, sin
importar `transferir_al_vencer`; el estado `cancelada` no se produce. La
devolución posterior la hace el barrido y se prueba en T14.
"""

from uuid import uuid4

import pytest

from app.services.operaciones_bolsa import ResultadoCancelar
from tests.services.apoyo_bolsas import conteos
from tests.services.apoyo_operaciones_bolsa import (
    FECHA_CORTA,
    SALDO_INICIAL,
    esperar_error,
    estado_bolsa,
    estados,
    hacer_aportar,
    hacer_cancelar,
    hacer_retirarse,
    nueva_bolsa,
    saldo_de,
    sin_reintentos,  # noqa: F401
    transacciones,
    usuarios,
)

pytestmark = pytest.mark.usefixtures("sin_reintentos")

BOLSA = "bolsa-ana-cena"
TODOS_RETIRADOS = {"ana": "retirado", "beto": "retirado", "carla": "retirado"}


@pytest.fixture
def tokens(bd):
    return usuarios(bd, "ana", "beto", "carla", "olga")


def _saldos(bd) -> dict[str, int]:
    return {c: saldo_de(bd, c) for c in ("ana", "beto", "carla", "olga", BOLSA)}


def test_cancelar_sin_pagos_cierra_la_bolsa(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    antes = conteos(bd)
    r = hacer_cancelar(bd, tokens["ana"], bolsa)
    assert r == ResultadoCancelar(estado_bolsa="cerrada")
    assert estado_bolsa(bd, bolsa) == "cerrada"
    assert estados(bd, bolsa) == TODOS_RETIRADOS
    assert conteos(bd) == antes
    assert saldo_de(bd, BOLSA) == 0


def test_cancelar_con_pagos_deja_liquidando_sin_mover_dinero(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens, transferir_al_vencer=False)
    hacer_aportar(bd, tokens["ana"], bolsa)
    hacer_aportar(bd, tokens["beto"], bolsa)
    conteos_antes = conteos(bd)
    saldos_antes = _saldos(bd)
    assert saldos_antes == {
        "ana": SALDO_INICIAL - 30_000,
        "beto": SALDO_INICIAL - 30_000,
        "carla": SALDO_INICIAL,
        "olga": SALDO_INICIAL,
        BOLSA: 60_000,
    }
    r = hacer_cancelar(bd, tokens["ana"], bolsa)
    assert r == ResultadoCancelar(estado_bolsa="liquidando")
    assert estado_bolsa(bd, bolsa) == "liquidando"
    assert estados(bd, bolsa) == TODOS_RETIRADOS
    assert conteos(bd) == conteos_antes
    assert _saldos(bd) == saldos_antes


def test_cancelar_con_transferir_al_vencer_tambien_devuelve(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens, transferir_al_vencer=True)
    hacer_aportar(bd, tokens["ana"], bolsa)
    hacer_aportar(bd, tokens["beto"], bolsa)
    r = hacer_cancelar(bd, tokens["ana"], bolsa)
    assert r == ResultadoCancelar(estado_bolsa="liquidando")
    assert estado_bolsa(bd, bolsa) == "liquidando"
    assert estados(bd, bolsa) == TODOS_RETIRADOS
    assert transacciones(bd, "transferencia_final") == []
    assert saldo_de(bd, BOLSA) == 60_000


def test_creador_retirado_puede_cancelar(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    hacer_aportar(bd, tokens["beto"], bolsa)
    hacer_retirarse(bd, tokens["ana"], bolsa)
    r = hacer_cancelar(bd, tokens["ana"], bolsa)
    assert r == ResultadoCancelar(estado_bolsa="liquidando")
    assert estados(bd, bolsa) == TODOS_RETIRADOS


def test_no_creador_recibe_sin_permiso(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    esperar_error(
        bd, "sin_permiso", lambda: hacer_cancelar(bd, tokens["beto"], bolsa), bolsa
    )
    assert estado_bolsa(bd, bolsa) == "abierta"


def test_no_participante_recibe_sin_permiso(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    esperar_error(
        bd, "sin_permiso", lambda: hacer_cancelar(bd, tokens["olga"], bolsa), bolsa
    )


def test_bolsa_inexistente_da_no_encontrado(bd, tokens):
    esperar_error(
        bd, "no_encontrado", lambda: hacer_cancelar(bd, tokens["ana"], uuid4())
    )


def test_cancelar_dos_veces_da_estado_invalido(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    hacer_aportar(bd, tokens["beto"], bolsa)
    assert hacer_cancelar(bd, tokens["ana"], bolsa).estado_bolsa == "liquidando"
    esperar_error(
        bd, "estado_invalido", lambda: hacer_cancelar(bd, tokens["ana"], bolsa), bolsa
    )


def test_cancelar_bolsa_cerrada_da_estado_invalido(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    for n in ("ana", "beto", "carla"):
        hacer_aportar(bd, tokens[n], bolsa)
    assert estado_bolsa(bd, bolsa) == "cerrada"
    esperar_error(
        bd, "estado_invalido", lambda: hacer_cancelar(bd, tokens["ana"], bolsa), bolsa
    )


def test_cancelar_en_la_fecha_limite_da_fuera_de_plazo(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    esperar_error(
        bd,
        "fuera_de_plazo",
        lambda: hacer_cancelar(bd, tokens["ana"], bolsa, ahora=FECHA_CORTA),
        bolsa,
    )
    assert estado_bolsa(bd, bolsa) == "abierta"


def test_estado_se_revisa_antes_que_el_plazo(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    hacer_aportar(bd, tokens["beto"], bolsa)
    hacer_cancelar(bd, tokens["ana"], bolsa)
    assert estado_bolsa(bd, bolsa) == "liquidando"
    esperar_error(
        bd,
        "estado_invalido",
        lambda: hacer_cancelar(bd, tokens["ana"], bolsa, ahora=FECHA_CORTA),
        bolsa,
    )
