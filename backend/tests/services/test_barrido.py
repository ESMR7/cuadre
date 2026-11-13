"""Barrido de vencidas (SPEC 7.2 a 7.4, 2.8 y 10.7; T14).

Datos por defecto: bolsa de $90.000 entre ana (creadora), beto y carla, partes
de $30.000, objetivo olga, fecha límite `FECHA_CORTA`. El barrido corre en
`FECHA_CORTA`. Cada prueba verifica montos exactos y, con
`verificar_devoluciones`, que hay a lo sumo una devolución por participante y
que nunca se devuelve más de lo aportado.
"""

import logging
from datetime import timedelta

import pytest
from sqlalchemy import text

from app import vencer
from app.db.invariantes import correr_invariantes
from app.services import barrido
from app.services.operaciones_bolsa import BolsaInconsistente
from tests.services.apoyo_barrido import (
    correr_barrido,
    hacer_devolver,
    hacer_preparar,
    verificar_devoluciones,
)
from tests.services.apoyo_bolsas import conteos
from tests.services.apoyo_operaciones_bolsa import (
    FECHA_CORTA,
    SALDO_INICIAL,
    Tx,
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

BOLSA = "bolsa-ana-cena"


@pytest.fixture
def t(bd):
    return usuarios(bd, "ana", "beto", "carla", "olga")


def _saldos(bd, *cuentas) -> dict[str, int]:
    return {c: saldo_de(bd, c) for c in cuentas}


def _devoluciones(bd) -> list[Tx]:
    return transacciones(bd, "devolucion")


def _finales(bd) -> list[Tx]:
    return transacciones(bd, "transferencia_final")


def _bolsa_pagada_por_ana_y_beto(bd, t, transferir: bool, nombre: str = "cena"):
    bolsa = nueva_bolsa(bd, t, nombre=nombre, transferir_al_vencer=transferir)
    hacer_aportar(bd, t["ana"], bolsa)
    hacer_aportar(bd, t["beto"], bolsa)
    return bolsa


def _bolsa_con_ana_por_confirmar(bd, t, objetivo="olga"):
    """$120.000 con dani: dani se retiró; beto y carla confirmaron; ana no."""
    bolsa = nueva_bolsa(
        bd,
        t,
        participantes=("ana", "beto", "carla", "dani"),
        total=120_000,
        cuenta_objetivo=objetivo,
    )
    for n in ("ana", "beto", "carla"):
        hacer_aportar(bd, t[n], bolsa)
    hacer_retirarse(bd, t["dani"], bolsa)
    for n in ("beto", "carla"):
        hacer_confirmar(bd, t[n], bolsa)
    assert estados(bd, bolsa)["ana"] == "por_confirmar"
    return bolsa


# --- Vencimiento con cada política (7.3) ---------------------------------


def test_vencimiento_con_transferir_envia_lo_de_los_pagados(bd, t):
    bolsa = _bolsa_pagada_por_ana_y_beto(bd, t, transferir=True)
    r = correr_barrido(bd)
    assert r.procesadas == [bolsa] and r.fallidas == []
    assert estado_bolsa(bd, bolsa) == "cerrada"
    assert estados(bd, bolsa) == {
        "ana": "pagado",
        "beto": "pagado",
        "carla": "retirado",
    }
    assert _finales(bd) == [Tx("transferencia_final", BOLSA, "olga", 60_000)]
    assert _devoluciones(bd) == []
    assert _saldos(bd, "ana", "beto", "carla", "olga", BOLSA) == {
        "ana": SALDO_INICIAL - 30_000,
        "beto": SALDO_INICIAL - 30_000,
        "carla": SALDO_INICIAL,
        "olga": SALDO_INICIAL + 60_000,
        BOLSA: 0,
    }
    verificar_devoluciones(bd)


def test_vencimiento_con_devolver_devuelve_todo(bd, t):
    bolsa = _bolsa_pagada_por_ana_y_beto(bd, t, transferir=False)
    r = correr_barrido(bd)
    assert r.procesadas == [bolsa] and r.fallidas == []
    assert estado_bolsa(bd, bolsa) == "cerrada"
    assert set(estados(bd, bolsa).values()) == {"retirado"}
    assert sorted(_devoluciones(bd), key=lambda x: x.destino) == [
        Tx("devolucion", BOLSA, "ana", 30_000),
        Tx("devolucion", BOLSA, "beto", 30_000),
    ]
    assert _finales(bd) == []
    assert _saldos(bd, "ana", "beto", "carla", "olga", BOLSA) == {
        "ana": SALDO_INICIAL,
        "beto": SALDO_INICIAL,
        "carla": SALDO_INICIAL,
        "olga": SALDO_INICIAL,
        BOLSA: 0,
    }
    verificar_devoluciones(bd)


def test_por_confirmar_se_retiran_y_se_les_devuelve(bd, t):
    t |= usuarios(bd, "dani")
    bolsa = _bolsa_con_ana_por_confirmar(bd, t)
    correr_barrido(bd)
    assert estado_bolsa(bd, bolsa) == "cerrada"
    assert estados(bd, bolsa) == {
        "ana": "retirado",
        "beto": "pagado",
        "carla": "pagado",
        "dani": "retirado",
    }
    assert _devoluciones(bd) == [Tx("devolucion", BOLSA, "ana", 30_000)]
    assert _finales(bd) == [Tx("transferencia_final", BOLSA, "olga", 60_000)]
    assert _saldos(bd, "ana", "beto", "carla", "dani", "olga", BOLSA) == {
        "ana": SALDO_INICIAL,
        "beto": SALDO_INICIAL - 30_000,
        "carla": SALDO_INICIAL - 30_000,
        "dani": SALDO_INICIAL,
        "olga": SALDO_INICIAL + 60_000,
        BOLSA: 0,
    }
    verificar_devoluciones(bd)


def test_vencimiento_sin_pagos_cierra_sin_mover_dinero(bd, t):
    bolsa = nueva_bolsa(bd, t)
    antes = conteos(bd)
    correr_barrido(bd)
    assert estado_bolsa(bd, bolsa) == "cerrada"
    assert set(estados(bd, bolsa).values()) == {"retirado"}
    assert conteos(bd) == antes
    assert saldo_de(bd, BOLSA) == 0
    verificar_devoluciones(bd)


def test_bolsa_vigente_no_se_toca(bd, t):
    bolsa = _bolsa_pagada_por_ana_y_beto(bd, t, transferir=True)
    antes = conteos(bd)
    r = correr_barrido(bd, FECHA_CORTA - timedelta(microseconds=1))
    assert r.procesadas == [] and r.fallidas == []
    assert estado_bolsa(bd, bolsa) == "abierta"
    assert conteos(bd) == antes
    assert saldo_de(bd, BOLSA) == 60_000


def test_bolsa_se_procesa_exactamente_en_la_fecha_limite(bd, t):
    bolsa = _bolsa_pagada_por_ana_y_beto(bd, t, transferir=True)
    correr_barrido(bd, FECHA_CORTA)
    assert estado_bolsa(bd, bolsa) == "cerrada"
    assert _finales(bd) == [Tx("transferencia_final", BOLSA, "olga", 60_000)]
    assert saldo_de(bd, BOLSA) == 0


# --- Reanudación y repetición (10.7) -------------------------------------


def test_reanudacion_no_paga_de_mas(bd, t):
    bolsa = _bolsa_pagada_por_ana_y_beto(bd, t, transferir=False)
    assert hacer_preparar(bd, bolsa) is True
    d = hacer_devolver(bd, bolsa, "ana")
    assert (d.tipo, d.origen, d.destino, d.monto) == (
        "devolucion",
        BOLSA,
        "ana",
        30_000,
    )
    # Estado intermedio válido (B9): liquidando con la deuda de beto pendiente.
    assert estado_bolsa(bd, bolsa) == "liquidando"
    assert saldo_de(bd, BOLSA) == 30_000
    r = correr_barrido(bd)
    assert r.fallidas == []
    assert estado_bolsa(bd, bolsa) == "cerrada"
    assert sorted(_devoluciones(bd), key=lambda x: x.destino) == [
        Tx("devolucion", BOLSA, "ana", 30_000),
        Tx("devolucion", BOLSA, "beto", 30_000),
    ]
    assert _saldos(bd, "ana", "beto", BOLSA) == {
        "ana": SALDO_INICIAL,
        "beto": SALDO_INICIAL,
        BOLSA: 0,
    }
    verificar_devoluciones(bd)


def test_devolver_dos_veces_al_mismo_no_paga_de_mas(bd, t):
    bolsa = _bolsa_pagada_por_ana_y_beto(bd, t, transferir=False)
    hacer_preparar(bd, bolsa)
    assert hacer_devolver(bd, bolsa, "ana").monto == 30_000
    assert hacer_devolver(bd, bolsa, "ana") is None
    assert saldo_de(bd, "ana") == SALDO_INICIAL
    assert saldo_de(bd, BOLSA) == 30_000
    verificar_devoluciones(bd)
    correr_barrido(bd)  # deja la bolsa cerrada para las invariantes
    assert saldo_de(bd, BOLSA) == 0


def test_dos_ejecuciones_seguidas_no_mueven_dinero(bd, t):
    bolsa = _bolsa_pagada_por_ana_y_beto(bd, t, transferir=False)
    correr_barrido(bd)
    antes = conteos(bd)
    saldos = _saldos(bd, "ana", "beto", "carla", "olga", BOLSA)
    r = correr_barrido(bd)
    assert r.procesadas == [] and r.fallidas == []
    assert conteos(bd) == antes
    assert _saldos(bd, "ana", "beto", "carla", "olga", BOLSA) == saldos
    assert saldos[BOLSA] == 0
    assert estado_bolsa(bd, bolsa) == "cerrada"
    verificar_devoluciones(bd)


def test_objetivo_participante_no_cuenta_como_devolucion(bd, t):
    """Deuda por tipo (2.8): la transferencia final hacia ana no es devolución."""
    t |= usuarios(bd, "dani")
    bolsa = _bolsa_con_ana_por_confirmar(bd, t, objetivo="ana")
    correr_barrido(bd)
    correr_barrido(bd)
    assert estado_bolsa(bd, bolsa) == "cerrada"
    assert _devoluciones(bd) == [Tx("devolucion", BOLSA, "ana", 30_000)]
    assert _finales(bd) == [Tx("transferencia_final", BOLSA, "ana", 60_000)]
    assert _saldos(bd, "ana", "beto", "carla", BOLSA) == {
        "ana": SALDO_INICIAL + 60_000,
        "beto": SALDO_INICIAL - 30_000,
        "carla": SALDO_INICIAL - 30_000,
        BOLSA: 0,
    }
    verificar_devoluciones(bd)


# --- Fallas (10.7 y 2.8) -------------------------------------------------


def test_bolsa_que_falla_no_detiene_a_las_demas(bd, t, monkeypatch, caplog):
    ids = [
        _bolsa_pagada_por_ana_y_beto(bd, t, transferir=False, nombre=n)
        for n in ("cena", "viaje", "regalo")
    ]
    fallida = ids[1]
    original = barrido.cerrar

    def cerrar_con_falla(sesion, bolsa_id, ahora):
        if bolsa_id == fallida:
            raise RuntimeError("falla inyectada")
        return original(sesion, bolsa_id, ahora)

    monkeypatch.setattr(barrido, "cerrar", cerrar_con_falla)
    with caplog.at_level(logging.ERROR, logger="app.barrido"):
        r = correr_barrido(bd)
    assert r.fallidas == [fallida]
    assert str(fallida) in caplog.text
    assert [estado_bolsa(bd, b) for b in ids] == ["cerrada", "liquidando", "cerrada"]
    # Las devoluciones de la fallida se hicieron antes de cerrar.
    for n in ("cena", "viaje", "regalo"):
        assert saldo_de(bd, f"bolsa-ana-{n}") == 0
    assert _saldos(bd, "ana", "beto") == {"ana": SALDO_INICIAL, "beto": SALDO_INICIAL}
    assert len(_devoluciones(bd)) == 6
    verificar_devoluciones(bd)

    monkeypatch.undo()
    r = correr_barrido(bd)
    assert r.procesadas == [fallida] and r.fallidas == []
    assert estado_bolsa(bd, fallida) == "cerrada"
    assert len(_devoluciones(bd)) == 6


def test_deuda_negativa_se_reporta_sin_mover_dinero(bd, t, monkeypatch, caplog):
    bolsa = _bolsa_pagada_por_ana_y_beto(bd, t, transferir=False)
    monkeypatch.setattr(barrido, "deuda_participante", lambda *a, **k: -1)
    hacer_preparar(bd, bolsa)
    antes = conteos(bd)
    with pytest.raises(BolsaInconsistente):
        hacer_devolver(bd, bolsa, "ana")
    with caplog.at_level(logging.ERROR, logger="app.barrido"):
        r = correr_barrido(bd)
    assert r.fallidas == [bolsa]
    assert str(bolsa) in caplog.text
    assert conteos(bd) == antes
    assert estado_bolsa(bd, bolsa) == "liquidando"
    assert saldo_de(bd, BOLSA) == 60_000
    verificar_devoluciones(bd)
    # Sin el reemplazo, el barrido termina el trabajo (estado válido para B9).
    monkeypatch.undo()
    correr_barrido(bd)
    assert estado_bolsa(bd, bolsa) == "cerrada"
    assert _saldos(bd, "ana", "beto", BOLSA) == {
        "ana": SALDO_INICIAL,
        "beto": SALDO_INICIAL,
        BOLSA: 0,
    }


@pytest.mark.sin_invariantes
def test_estado_invalido_h2_no_transfiere_y_b9_lo_reporta(bd, t, motor_prueba, caplog):
    """Estado inválido H2 con SQL directo.

    SPEC 10.7: "Estado inválido (H2 de la auditoría): con SQL directo se deja
    una bolsa en `liquidando`, con la política de devolver y un participante
    en `pagado`. El barrido no hace la transferencia final, registra el error
    y B9 reporta la bolsa. Es una excepción como las de 10.5."
    AGENTS.md: "`TRUNCATE`, `UPDATE` y `DELETE` sobre el libro solo se
    permiten en esos fixtures, en las pruebas de las invariantes y en la
    prueba del estado inválido del barrido."
    Es el único lugar de T14 con UPDATE directo y `sin_invariantes`.
    """
    bolsa = _bolsa_pagada_por_ana_y_beto(bd, t, transferir=False)
    with bd() as sesion, sesion.begin():
        sesion.execute(
            text("UPDATE bolsas SET estado = 'liquidando' WHERE id = :b"),
            {"b": bolsa},
        )
    antes = conteos(bd)
    with caplog.at_level(logging.ERROR, logger="app.barrido"):
        r = correr_barrido(bd)
    assert r.fallidas == [bolsa]
    assert str(bolsa) in caplog.text
    assert conteos(bd) == antes
    assert _finales(bd) == [] and _devoluciones(bd) == []
    assert estado_bolsa(bd, bolsa) == "liquidando"
    assert saldo_de(bd, BOLSA) == 60_000
    assert saldo_de(bd, "olga") == SALDO_INICIAL
    b9 = correr_invariantes(motor_prueba, ["B9"])["B9"]
    # carla sigue en pendiente porque el UPDATE directo se salta preparar, y
    # B9 la reporta con razón: pendiente solo existe en bolsas abiertas.
    assert {(str(f[0]), f[1]) for f in b9} == {
        (str(bolsa), "ana"),
        (str(bolsa), "beto"),
        (str(bolsa), "carla"),
    }


# --- Comando (recorte 3) -------------------------------------------------


def test_comando_lee_el_reloj_una_vez_y_procesa(bd, t):
    bolsa = _bolsa_pagada_por_ana_y_beto(bd, t, transferir=False)
    llamadas = []

    def reloj():
        llamadas.append(1)
        return FECHA_CORTA

    assert vencer.main(reloj=reloj, fabrica=bd) == 0
    assert llamadas == [1]
    assert estado_bolsa(bd, bolsa) == "cerrada"
    assert _saldos(bd, "ana", "beto", BOLSA) == {
        "ana": SALDO_INICIAL,
        "beto": SALDO_INICIAL,
        BOLSA: 0,
    }
    verificar_devoluciones(bd)


def test_comando_devuelve_1_si_una_bolsa_falla(bd, t, monkeypatch):
    bolsa = _bolsa_pagada_por_ana_y_beto(bd, t, transferir=False)

    def cerrar_con_falla(sesion, bolsa_id, ahora):
        raise RuntimeError("falla inyectada")

    monkeypatch.setattr(barrido, "cerrar", cerrar_con_falla)
    assert vencer.main(reloj=lambda: FECHA_CORTA, fabrica=bd) == 1
    assert estado_bolsa(bd, bolsa) == "liquidando"
    monkeypatch.undo()
    assert vencer.main(reloj=lambda: FECHA_CORTA, fabrica=bd) == 0
    assert estado_bolsa(bd, bolsa) == "cerrada"
    assert saldo_de(bd, BOLSA) == 0
