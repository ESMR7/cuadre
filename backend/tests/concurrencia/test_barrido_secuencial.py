"""Filas de vencimiento de la tabla 8.4, sin hilos (T14).

A y luego B, y B y luego A. B es siempre el barrido, `procesar_vencidas` en
`FECHA_CORTA`; A es la operación de usuario, que llega antes de la fecha
límite (`AHORA`). La cancelación usa el resultado del recorte 2 (DECISIONS.md,
2026-11-13). Incluye la devolución pendiente de la fila "retiro contra
cancelación" de T13. Cada prueba verifica montos exactos, saldo final 0 en la
bolsa y, con `verificar_devoluciones`, a lo sumo una devolución por
participante y nunca más de lo aportado. El fixture `sin_reintentos` de esta
carpeta exige cero reintentos.
"""

import pytest

from tests.services.apoyo_barrido import correr_barrido, verificar_devoluciones
from tests.services.apoyo_libro import AHORA
from tests.services.apoyo_operaciones_bolsa import (
    SALDO_INICIAL,
    Tx,
    estado_bolsa,
    estados,
    hacer_aportar,
    hacer_cancelar,
    hacer_confirmar,
    hacer_retirarse,
    nueva_bolsa,
    resultado,
    saldo_de,
    transacciones,
    usuarios,
)

ORDENES = pytest.mark.parametrize("a_primero", [True, False], ids=["A_B", "B_A"])
BOLSA = "bolsa-ana-cena"


def correr(a_primero, a, b):
    if a_primero:
        ra = resultado(a)
        rb = resultado(b)
    else:
        rb = resultado(b)
        ra = resultado(a)
    return ra, rb


def finales(bd) -> list[Tx]:
    return transacciones(bd, "transferencia_final")


def devoluciones(bd) -> list[Tx]:
    return sorted(transacciones(bd, "devolucion"), key=lambda t: t.destino)


def saldos(bd, *cuentas) -> dict[str, int]:
    return {c: saldo_de(bd, c) for c in cuentas}


def _ana_y_beto_pagaron(bd, t, transferir=True):
    bolsa = nueva_bolsa(bd, t, transferir_al_vencer=transferir)
    hacer_aportar(bd, t["ana"], bolsa)
    hacer_aportar(bd, t["beto"], bolsa)
    return bolsa


@ORDENES
def test_ultimo_aporte_contra_vencimiento(bd, a_primero):
    t = usuarios(bd, "ana", "beto", "carla", "olga")
    bolsa = _ana_y_beto_pagaron(bd, t)
    ra, rb = correr(
        a_primero,
        lambda: hacer_aportar(bd, t["carla"], bolsa),
        lambda: correr_barrido(bd),
    )
    assert estado_bolsa(bd, bolsa) == "cerrada"
    assert devoluciones(bd) == []
    if a_primero:
        assert ra[0] == "ok"
        assert rb[1].procesadas == [] and rb[1].fallidas == []
        assert finales(bd) == [Tx("transferencia_final", BOLSA, "olga", 90_000)]
        assert saldos(bd, "carla", "olga", BOLSA) == {
            "carla": SALDO_INICIAL - 30_000,
            "olga": SALDO_INICIAL + 90_000,
            BOLSA: 0,
        }
    else:
        assert rb[1].fallidas == []
        assert ra == ("error", "estado_invalido")
        assert estados(bd, bolsa)["carla"] == "retirado"
        assert finales(bd) == [Tx("transferencia_final", BOLSA, "olga", 60_000)]
        assert saldos(bd, "carla", "olga", BOLSA) == {
            "carla": SALDO_INICIAL,
            "olga": SALDO_INICIAL + 60_000,
            BOLSA: 0,
        }
    verificar_devoluciones(bd)


@ORDENES
def test_ultima_confirmacion_contra_vencimiento(bd, a_primero):
    t = usuarios(bd, "ana", "beto", "carla", "dani", "olga")
    bolsa = nueva_bolsa(
        bd, t, participantes=("ana", "beto", "carla", "dani"), total=120_000
    )
    for n in ("ana", "beto", "carla"):
        hacer_aportar(bd, t[n], bolsa)
    hacer_retirarse(bd, t["dani"], bolsa)
    for n in ("beto", "carla"):
        hacer_confirmar(bd, t[n], bolsa)
    ra, rb = correr(
        a_primero,
        lambda: hacer_confirmar(bd, t["ana"], bolsa),
        lambda: correr_barrido(bd),
    )
    assert rb[0] == "ok" and rb[1].fallidas == []
    assert estado_bolsa(bd, bolsa) == "cerrada"
    if a_primero:
        assert ra[1].estado_bolsa == "cerrada"
        assert devoluciones(bd) == []
        assert finales(bd) == [Tx("transferencia_final", BOLSA, "olga", 90_000)]
        assert saldos(bd, "ana", "olga", BOLSA) == {
            "ana": SALDO_INICIAL - 30_000,
            "olga": SALDO_INICIAL + 90_000,
            BOLSA: 0,
        }
    else:
        assert ra == ("error", "estado_invalido")
        assert devoluciones(bd) == [Tx("devolucion", BOLSA, "ana", 30_000)]
        assert finales(bd) == [Tx("transferencia_final", BOLSA, "olga", 60_000)]
        assert saldos(bd, "ana", "olga", BOLSA) == {
            "ana": SALDO_INICIAL,
            "olga": SALDO_INICIAL + 60_000,
            BOLSA: 0,
        }
    verificar_devoluciones(bd)


@ORDENES
def test_retiro_contra_vencimiento_con_transferir(bd, a_primero):
    t = usuarios(bd, "ana", "beto", "carla", "olga")
    bolsa = _ana_y_beto_pagaron(bd, t, transferir=True)
    ra, rb = correr(
        a_primero,
        lambda: hacer_retirarse(bd, t["beto"], bolsa),
        lambda: correr_barrido(bd),
    )
    assert rb[0] == "ok" and rb[1].fallidas == []
    assert estado_bolsa(bd, bolsa) == "cerrada"
    if a_primero:
        assert ra[1].devolucion.monto == 30_000
        assert devoluciones(bd) == [
            Tx("devolucion", BOLSA, "ana", 30_000),
            Tx("devolucion", BOLSA, "beto", 30_000),
        ]
        assert finales(bd) == []
        assert saldos(bd, "ana", "beto", "olga", BOLSA) == {
            "ana": SALDO_INICIAL,
            "beto": SALDO_INICIAL,
            "olga": SALDO_INICIAL,
            BOLSA: 0,
        }
    else:
        assert ra == ("error", "estado_invalido")
        assert devoluciones(bd) == []
        assert finales(bd) == [Tx("transferencia_final", BOLSA, "olga", 60_000)]
        assert saldos(bd, "ana", "beto", "olga", BOLSA) == {
            "ana": SALDO_INICIAL - 30_000,
            "beto": SALDO_INICIAL - 30_000,
            "olga": SALDO_INICIAL + 60_000,
            BOLSA: 0,
        }
    verificar_devoluciones(bd)


@ORDENES
def test_retiro_contra_vencimiento_con_devolver(bd, a_primero):
    t = usuarios(bd, "ana", "beto", "carla", "olga")
    bolsa = _ana_y_beto_pagaron(bd, t, transferir=False)
    ra, rb = correr(
        a_primero,
        lambda: hacer_retirarse(bd, t["beto"], bolsa),
        lambda: correr_barrido(bd),
    )
    assert rb[0] == "ok" and rb[1].fallidas == []
    if a_primero:
        assert ra[1].devolucion.monto == 30_000
    else:
        assert ra == ("error", "estado_invalido")
    assert estado_bolsa(bd, bolsa) == "cerrada"
    assert devoluciones(bd) == [
        Tx("devolucion", BOLSA, "ana", 30_000),
        Tx("devolucion", BOLSA, "beto", 30_000),
    ]
    assert finales(bd) == []
    assert saldos(bd, "ana", "beto", "olga", BOLSA) == {
        "ana": SALDO_INICIAL,
        "beto": SALDO_INICIAL,
        "olga": SALDO_INICIAL,
        BOLSA: 0,
    }
    verificar_devoluciones(bd)


@ORDENES
def test_cancelacion_contra_vencimiento(bd, a_primero):
    """Política de transferir (datos por defecto); ana y beto pagaron."""
    t = usuarios(bd, "ana", "beto", "carla", "olga")
    bolsa = _ana_y_beto_pagaron(bd, t, transferir=True)
    ra, rb = correr(
        a_primero,
        lambda: hacer_cancelar(bd, t["ana"], bolsa),
        lambda: correr_barrido(bd),
    )
    assert estado_bolsa(bd, bolsa) == "cerrada"
    if a_primero:
        assert ra[1].estado_bolsa == "liquidando"
        assert rb[1].procesadas == [bolsa] and rb[1].fallidas == []
        assert devoluciones(bd) == [
            Tx("devolucion", BOLSA, "ana", 30_000),
            Tx("devolucion", BOLSA, "beto", 30_000),
        ]
        assert finales(bd) == []
        assert saldos(bd, "ana", "beto", "olga", BOLSA) == {
            "ana": SALDO_INICIAL,
            "beto": SALDO_INICIAL,
            "olga": SALDO_INICIAL,
            BOLSA: 0,
        }
    else:
        assert ra == ("error", "estado_invalido")
        assert devoluciones(bd) == []
        assert finales(bd) == [Tx("transferencia_final", BOLSA, "olga", 60_000)]
        assert saldos(bd, "ana", "beto", "olga", BOLSA) == {
            "ana": SALDO_INICIAL - 30_000,
            "beto": SALDO_INICIAL - 30_000,
            "olga": SALDO_INICIAL + 60_000,
            BOLSA: 0,
        }
    verificar_devoluciones(bd)


@ORDENES
def test_retiro_contra_cancelacion_y_luego_barrido(bd, a_primero):
    """Completa la fila de T13: el barrido hace la devolución pendiente."""
    t = usuarios(bd, "ana", "beto", "carla", "olga")
    bolsa = _ana_y_beto_pagaron(bd, t, transferir=False)
    ra, rb = correr(
        a_primero,
        lambda: hacer_retirarse(bd, t["beto"], bolsa),
        lambda: hacer_cancelar(bd, t["ana"], bolsa),
    )
    assert rb[1].estado_bolsa == "liquidando"
    if a_primero:
        assert ra[1].devolucion.monto == 30_000
    else:
        assert ra == ("error", "estado_invalido")
    # Una bolsa en liquidando se procesa aunque no haya vencido.
    r = correr_barrido(bd, ahora=AHORA)
    assert r.procesadas == [bolsa] and r.fallidas == []
    assert estado_bolsa(bd, bolsa) == "cerrada"
    assert devoluciones(bd) == [
        Tx("devolucion", BOLSA, "ana", 30_000),
        Tx("devolucion", BOLSA, "beto", 30_000),
    ]
    assert finales(bd) == []
    assert saldos(bd, "ana", "beto", "carla", "olga", BOLSA) == {
        "ana": SALDO_INICIAL,
        "beto": SALDO_INICIAL,
        "carla": SALDO_INICIAL,
        "olga": SALDO_INICIAL,
        BOLSA: 0,
    }
    verificar_devoluciones(bd)
