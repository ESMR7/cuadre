"""Consultas de bolsas con dinero movido: pendientes de T10 (SPEC 9.4, T11)."""

import pytest

from app.services.bolsas import ConteoParticipantes, MiParticipacion
from tests.services.apoyo_operaciones_bolsa import (
    hacer_aportar,
    hacer_retirarse,
    nueva_bolsa,
    sin_reintentos,  # noqa: F401
    usuarios,
)
from tests.services.test_bolsas_consultas import detalle, movimientos

pytestmark = pytest.mark.usefixtures("sin_reintentos")


@pytest.fixture
def tokens(bd):
    return usuarios(bd, "ana", "beto", "carla", "olga")


def test_aportado_refleja_aportes_y_devoluciones(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    hacer_aportar(bd, tokens["ana"], bolsa)
    hacer_aportar(bd, tokens["beto"], bolsa)
    assert detalle(bd, tokens["ana"], bolsa).aportado == 60_000
    hacer_retirarse(bd, tokens["beto"], bolsa)
    assert detalle(bd, tokens["ana"], bolsa).aportado == 30_000


def test_transferido_muestra_el_monto_de_la_transferencia_final(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    for n in ("ana", "beto"):
        hacer_aportar(bd, tokens[n], bolsa)
    assert detalle(bd, tokens["ana"], bolsa).transferido is None
    hacer_aportar(bd, tokens["carla"], bolsa)
    d = detalle(bd, tokens["ana"], bolsa)
    assert d.transferido == 90_000
    assert d.aportado == 0
    assert d.estado == "cerrada"


def test_meta_baja_con_un_retirado_y_conteos_cambian(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens, total=100_000)  # ana 33.334, otros 33.333
    hacer_aportar(bd, tokens["ana"], bolsa)
    hacer_retirarse(bd, tokens["carla"], bolsa)
    d = detalle(bd, tokens["beto"], bolsa)
    assert d.meta == 66_667
    assert d.total == 100_000
    assert d.participantes == ConteoParticipantes(
        total=3, pendientes=1, pagados=0, por_confirmar=1, retirados=1
    )


def test_mis_movimientos_con_la_bolsa_con_signo_y_sin_transferencia_final(bd, tokens):
    """ana es participante y cuenta objetivo: la transferencia final no aparece."""
    bolsa = nueva_bolsa(bd, tokens, cuenta_objetivo="ana")
    hacer_aportar(bd, tokens["ana"], bolsa)
    hacer_retirarse(bd, tokens["carla"], bolsa)  # ana pasa a por_confirmar
    hacer_retirarse(bd, tokens["ana"], bolsa)  # devolución de 30.000
    hacer_aportar(bd, tokens["beto"], bolsa)  # beto único activo: completa
    vistos = [
        (m.tipo, m.contrapartida, m.monto)
        for m in movimientos(bd, tokens["ana"], bolsa)
    ]
    assert vistos == [
        ("devolucion", "bolsa-ana-cena", 30_000),
        ("aporte", "bolsa-ana-cena", -30_000),
    ]
    assert detalle(bd, tokens["ana"], bolsa).transferido == 30_000


def test_retirado_sigue_viendo_la_bolsa(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    hacer_aportar(bd, tokens["beto"], bolsa)
    hacer_retirarse(bd, tokens["beto"], bolsa)
    d = detalle(bd, tokens["beto"], bolsa)
    assert d.mi_participacion == MiParticipacion(30_000, "retirado")
    assert [m.tipo for m in movimientos(bd, tokens["beto"], bolsa)] == [
        "devolucion",
        "aporte",
    ]
