"""Filas de bolsas de la tabla 8.4 sin vencimiento (T11 y T13).

Las filas de cancelación (T13) usan el resultado del recorte 2
(DECISIONS.md, 2026-11-13): cancelar siempre retira a todos; la bolsa queda
`liquidando` y la devolución la hace el barrido (T14).

Dos pruebas por fila, sin hilos: A y luego B, y B y luego A, con los datos de
partida de la tabla (bolsa de $90.000 entre ana, beto y carla, partes de
$30.000, objetivo olga y política de transferir, salvo que la fila diga
otra cosa). Cada operación usa su propia sesión. El fixture `sin_reintentos`
de esta carpeta exige cero reintentos.
"""

from uuid import uuid4

import pytest

from app.services.nucleo import transferir
from tests.services.apoyo_bolsas import crear
from tests.services.apoyo_libro import AHORA
from tests.services.apoyo_operaciones_bolsa import (
    SALDO_INICIAL,
    Tx,
    cargar_saldo,
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
    """Corre A y B en el orden pedido y devuelve (resultado A, resultado B)."""
    if a_primero:
        ra = resultado(a)
        rb = resultado(b)
    else:
        rb = resultado(b)
        ra = resultado(a)
    return ra, rb


def finales(bd) -> list[Tx]:
    return transacciones(bd, "transferencia_final")


# --- Dos últimos pendientes aportan --------------------------------------


@ORDENES
def test_dos_ultimos_pendientes_aportan(bd, a_primero):
    t = usuarios(bd, "ana", "beto", "carla", "olga")
    bolsa = nueva_bolsa(bd, t)
    hacer_aportar(bd, t["ana"], bolsa)
    ra, rb = correr(
        a_primero,
        lambda: hacer_aportar(bd, t["beto"], bolsa),
        lambda: hacer_aportar(bd, t["carla"], bolsa),
    )
    assert ra[0] == rb[0] == "ok"
    assert finales(bd) == [Tx("transferencia_final", BOLSA, "olga", 90_000)]
    assert estado_bolsa(bd, bolsa) == "cerrada"
    assert set(estados(bd, bolsa).values()) == {"pagado"}
    assert saldo_de(bd, BOLSA) == 0


# --- Último aporte contra el retiro de otro ------------------------------


@ORDENES
def test_ultimo_aporte_contra_el_retiro_de_otro(bd, a_primero):
    t = usuarios(bd, "ana", "beto", "carla", "olga")
    bolsa = nueva_bolsa(bd, t)
    hacer_aportar(bd, t["ana"], bolsa)
    hacer_aportar(bd, t["beto"], bolsa)
    ra, rb = correr(
        a_primero,
        lambda: hacer_aportar(bd, t["carla"], bolsa),
        lambda: hacer_retirarse(bd, t["beto"], bolsa),
    )
    if a_primero:
        assert ra[0] == "ok"
        assert rb == ("error", "estado_invalido")
        assert finales(bd) == [Tx("transferencia_final", BOLSA, "olga", 90_000)]
        assert estado_bolsa(bd, bolsa) == "cerrada"
        assert saldo_de(bd, "beto") == SALDO_INICIAL - 30_000
    else:
        assert rb[0] == "ok"
        assert rb[1].devolucion.monto == 30_000
        assert ra[0] == "ok"
        assert saldo_de(bd, "beto") == SALDO_INICIAL
        assert estados(bd, bolsa) == {
            "ana": "por_confirmar",
            "beto": "retirado",
            "carla": "pagado",
        }
        assert estado_bolsa(bd, bolsa) == "abierta"
        assert finales(bd) == []
        assert saldo_de(bd, BOLSA) == 60_000


# --- Último aporte contra el retiro del único otro participante ----------


@ORDENES
def test_ultimo_aporte_contra_el_retiro_del_unico_otro(bd, a_primero):
    t = usuarios(bd, "ana", "beto", "olga")
    bolsa = nueva_bolsa(bd, t, participantes=("ana", "beto"), total=60_000)
    hacer_aportar(bd, t["beto"], bolsa)
    ra, rb = correr(
        a_primero,
        lambda: hacer_aportar(bd, t["ana"], bolsa),
        lambda: hacer_retirarse(bd, t["beto"], bolsa),
    )
    assert ra[0] == "ok"
    assert estado_bolsa(bd, bolsa) == "cerrada"
    assert saldo_de(bd, BOLSA) == 0
    if a_primero:
        assert rb == ("error", "estado_invalido")
        assert finales(bd) == [Tx("transferencia_final", BOLSA, "olga", 60_000)]
    else:
        assert rb[1].devolucion.monto == 30_000
        assert saldo_de(bd, "beto") == SALDO_INICIAL
        assert finales(bd) == [Tx("transferencia_final", BOLSA, "olga", 30_000)]


# --- Confirmaciones ------------------------------------------------------


def _bolsa_con_dani_retirado(bd, t, confirmados):
    """Bolsa de $120.000 con dani; dani se retiró y `confirmados` confirmaron."""
    bolsa = nueva_bolsa(
        bd, t, participantes=("ana", "beto", "carla", "dani"), total=120_000
    )
    for n in ("ana", "beto", "carla"):
        hacer_aportar(bd, t[n], bolsa)
    hacer_retirarse(bd, t["dani"], bolsa)
    for n in confirmados:
        hacer_confirmar(bd, t[n], bolsa)
    return bolsa


@ORDENES
def test_ultima_confirmacion_contra_un_retiro(bd, a_primero):
    t = usuarios(bd, "ana", "beto", "carla", "dani", "olga")
    bolsa = _bolsa_con_dani_retirado(bd, t, ("beto", "carla"))
    ra, rb = correr(
        a_primero,
        lambda: hacer_confirmar(bd, t["ana"], bolsa),
        lambda: hacer_retirarse(bd, t["beto"], bolsa),
    )
    if a_primero:
        assert ra == ("ok", ra[1]) and ra[1].estado_bolsa == "cerrada"
        assert rb == ("error", "estado_invalido")
        assert finales(bd) == [Tx("transferencia_final", BOLSA, "olga", 90_000)]
    else:
        assert rb[1].devolucion.monto == 30_000
        assert ra[1].estado_bolsa == "abierta"
        assert ra[1].mi_estado == "pagado"
        assert estados(bd, bolsa) == {
            "ana": "pagado",
            "beto": "retirado",
            "carla": "por_confirmar",
            "dani": "retirado",
        }
        assert finales(bd) == []


@ORDENES
def test_dos_confirmaciones_finales(bd, a_primero):
    t = usuarios(bd, "ana", "beto", "carla", "dani", "olga")
    bolsa = _bolsa_con_dani_retirado(bd, t, ("carla",))
    ra, rb = correr(
        a_primero,
        lambda: hacer_confirmar(bd, t["ana"], bolsa),
        lambda: hacer_confirmar(bd, t["beto"], bolsa),
    )
    primero, segundo = (ra, rb) if a_primero else (rb, ra)
    assert primero[1].estado_bolsa == "abierta"
    assert segundo[1].estado_bolsa == "cerrada"
    assert finales(bd) == [Tx("transferencia_final", BOLSA, "olga", 90_000)]
    assert saldo_de(bd, BOLSA) == 0


# --- Retiros -------------------------------------------------------------


@ORDENES
def test_retiro_de_los_dos_ultimos_activos(bd, a_primero):
    t = usuarios(bd, "ana", "beto", "carla", "olga")
    bolsa = nueva_bolsa(bd, t)
    hacer_aportar(bd, t["ana"], bolsa)
    hacer_aportar(bd, t["beto"], bolsa)
    hacer_retirarse(bd, t["carla"], bolsa)  # ana y beto en por_confirmar
    ra, rb = correr(
        a_primero,
        lambda: hacer_retirarse(bd, t["ana"], bolsa),
        lambda: hacer_retirarse(bd, t["beto"], bolsa),
    )
    assert ra[1].devolucion.monto == rb[1].devolucion.monto == 30_000
    assert estado_bolsa(bd, bolsa) == "cerrada"
    assert saldo_de(bd, BOLSA) == 0
    assert finales(bd) == []
    assert saldo_de(bd, "ana") == saldo_de(bd, "beto") == SALDO_INICIAL


@ORDENES
def test_retiro_repetido_con_otra_clave(bd, a_primero):
    t = usuarios(bd, "ana", "beto", "carla", "olga")
    bolsa = nueva_bolsa(bd, t)
    hacer_aportar(bd, t["beto"], bolsa)
    ra, rb = correr(
        a_primero,
        lambda: hacer_retirarse(bd, t["beto"], bolsa, uuid4()),
        lambda: hacer_retirarse(bd, t["beto"], bolsa, uuid4()),
    )
    primero, segundo = (ra, rb) if a_primero else (rb, ra)
    assert primero[1].devolucion.monto == 30_000
    assert segundo == ("error", "estado_invalido")
    assert len(transacciones(bd, "devolucion")) == 1
    assert saldo_de(bd, "beto") == SALDO_INICIAL


# --- Choques con el núcleo -----------------------------------------------


@ORDENES
def test_aporte_contra_transferencia_saliente_del_mismo_pagador(bd, a_primero):
    t = usuarios(bd, "ana", "beto", "olga")
    t.update(usuarios(bd, "carla", saldo=0))
    cargar_saldo(bd, t["carla"], 40_000)
    bolsa = nueva_bolsa(bd, t)

    def transferencia():
        with bd() as sesion:
            return transferir(sesion, t["carla"], uuid4(), "beto", 20_000, AHORA)

    ra, rb = correr(
        a_primero, lambda: hacer_aportar(bd, t["carla"], bolsa), transferencia
    )
    if a_primero:
        assert ra[0] == "ok"
        assert rb == ("error", "saldo_insuficiente")
        assert saldo_de(bd, "carla") == 10_000
    else:
        assert rb[0] == "ok"
        assert ra == ("error", "saldo_insuficiente")
        assert saldo_de(bd, "carla") == 20_000


@ORDENES
def test_aportes_del_mismo_usuario_a_dos_bolsas(bd, a_primero):
    t = usuarios(bd, "ana", "beto", "olga")
    t.update(usuarios(bd, "carla", saldo=0))
    cargar_saldo(bd, t["carla"], 60_000)
    una = nueva_bolsa(bd, t, nombre="una")
    otra = nueva_bolsa(bd, t, creador="beto", nombre="otra")
    ra, rb = correr(
        a_primero,
        lambda: hacer_aportar(bd, t["carla"], una),
        lambda: hacer_aportar(bd, t["carla"], otra),
    )
    assert ra[0] == rb[0] == "ok"
    assert saldo_de(bd, "carla") == 0
    assert saldo_de(bd, "bolsa-ana-una") == saldo_de(bd, "bolsa-beto-otra") == 30_000


@ORDENES
def test_crear_bolsa_contra_transferencia_entre_creador_y_objetivo(bd, a_primero):
    t = usuarios(bd, "ana", "beto", "carla", "olga")

    def transferencia():
        with bd() as sesion:
            return transferir(sesion, t["olga"], uuid4(), "ana", 10_000, AHORA)

    ra, rb = correr(a_primero, lambda: crear(bd, t["ana"]), transferencia)
    assert ra[0] == rb[0] == "ok"
    assert ra[1].estado == "abierta"
    assert saldo_de(bd, "ana") == SALDO_INICIAL + 10_000
    assert saldo_de(bd, "olga") == SALDO_INICIAL - 10_000


# --- Cancelación (T13, recorte 2) ----------------------------------------


@ORDENES
def test_ultimo_aporte_contra_cancelacion(bd, a_primero):
    t = usuarios(bd, "ana", "beto", "carla", "olga")
    bolsa = nueva_bolsa(bd, t)
    hacer_aportar(bd, t["ana"], bolsa)
    hacer_aportar(bd, t["beto"], bolsa)
    ra, rb = correr(
        a_primero,
        lambda: hacer_aportar(bd, t["carla"], bolsa),
        lambda: hacer_cancelar(bd, t["ana"], bolsa),
    )
    if a_primero:
        assert ra[0] == "ok"
        assert rb == ("error", "estado_invalido")
        assert finales(bd) == [Tx("transferencia_final", BOLSA, "olga", 90_000)]
        assert estado_bolsa(bd, bolsa) == "cerrada"
        assert saldo_de(bd, BOLSA) == 0
    else:
        assert rb[0] == "ok"
        assert rb[1].estado_bolsa == "liquidando"
        assert ra == ("error", "estado_invalido")
        assert estados(bd, bolsa) == {
            "ana": "retirado",
            "beto": "retirado",
            "carla": "retirado",
        }
        assert estado_bolsa(bd, bolsa) == "liquidando"
        assert finales(bd) == []
        assert saldo_de(bd, BOLSA) == 60_000
        assert saldo_de(bd, "carla") == SALDO_INICIAL


@ORDENES
def test_retiro_contra_cancelacion(bd, a_primero):
    t = usuarios(bd, "ana", "beto", "carla", "olga")
    bolsa = nueva_bolsa(bd, t, transferir_al_vencer=False)
    hacer_aportar(bd, t["ana"], bolsa)
    hacer_aportar(bd, t["beto"], bolsa)
    ra, rb = correr(
        a_primero,
        lambda: hacer_retirarse(bd, t["beto"], bolsa),
        lambda: hacer_cancelar(bd, t["ana"], bolsa),
    )
    assert rb[0] == "ok"
    assert rb[1].estado_bolsa == "liquidando"
    assert estados(bd, bolsa) == {
        "ana": "retirado",
        "beto": "retirado",
        "carla": "retirado",
    }
    assert estado_bolsa(bd, bolsa) == "liquidando"
    assert finales(bd) == []
    assert saldo_de(bd, "ana") == SALDO_INICIAL - 30_000
    if a_primero:
        assert ra[1].devolucion.monto == 30_000
        assert saldo_de(bd, "beto") == SALDO_INICIAL
        assert saldo_de(bd, BOLSA) == 30_000
    else:
        assert ra == ("error", "estado_invalido")
        assert saldo_de(bd, "beto") == SALDO_INICIAL - 30_000
        assert saldo_de(bd, BOLSA) == 60_000


@ORDENES
def test_ultima_confirmacion_contra_cancelacion(bd, a_primero):
    """Datos de "última confirmación contra un retiro" con carla de creadora."""
    t = usuarios(bd, "ana", "beto", "carla", "dani", "olga")
    bolsa = nueva_bolsa(
        bd,
        t,
        creador="carla",
        participantes=("ana", "beto", "carla", "dani"),
        total=120_000,
    )
    cuenta = "bolsa-carla-cena"
    for n in ("ana", "beto", "carla"):
        hacer_aportar(bd, t[n], bolsa)
    hacer_retirarse(bd, t["dani"], bolsa)
    for n in ("beto", "carla"):
        hacer_confirmar(bd, t[n], bolsa)
    assert estados(bd, bolsa)["ana"] == "por_confirmar"
    ra, rb = correr(
        a_primero,
        lambda: hacer_confirmar(bd, t["ana"], bolsa),
        lambda: hacer_cancelar(bd, t["carla"], bolsa),
    )
    if a_primero:
        assert ra[1].estado_bolsa == "cerrada"
        assert rb == ("error", "estado_invalido")
        assert finales(bd) == [Tx("transferencia_final", cuenta, "olga", 90_000)]
        assert saldo_de(bd, cuenta) == 0
    else:
        assert rb[0] == "ok"
        assert rb[1].estado_bolsa == "liquidando"
        assert ra == ("error", "estado_invalido")
        assert estados(bd, bolsa) == {
            "ana": "retirado",
            "beto": "retirado",
            "carla": "retirado",
            "dani": "retirado",
        }
        assert estado_bolsa(bd, bolsa) == "liquidando"
        assert finales(bd) == []
        assert saldo_de(bd, cuenta) == 90_000
