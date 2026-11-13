"""Filas de bolsas de la tabla 8.4 con hilos (SPEC 10.4), sin cancelación ni
vencimiento (T12), más los dos barridos a la vez (T14).

Cada fila se repite 10 veces con `parametrize`: cada repetición es un caso
nuevo, así que el fixture `bd` corre las invariantes y vacía la base entre
repeticiones y los datos de partida se crean de cero.

Cada prueba verifica:
1. El resultado es una de las ramas permitidas por la tabla, con el estado
   final exacto de esa rama.
2. Las reglas que valen en cualquier orden: a lo sumo una transferencia
   final (exactamente una si la bolsa se completa), ninguna devolución doble
   y el libro coherente con el saldo de la bolsa.
3. Ningún resultado `reintentos_agotados` (se revisa sobre los resultados
   envueltos, porque el envoltorio captura el ErrorDominio).
4. Cero reintentos de cualquier código, 40P01 incluido.
Las invariantes las corre el fixture `bd`. Sin sleep: el solapamiento lo da
la barrera.
"""

from collections import Counter
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.domain.errores import ErrorDominio
from app.services.barrido import procesar_vencidas
from app.services.bolsas import crear_bolsa
from app.services.nucleo import transferir
from app.services.operaciones_bolsa import aportar, confirmar, retirarse
from app.services.reintentos import reintentos_por_codigo
from tests.concurrencia.apoyo_hilos import correr_en_hilos
from tests.services.apoyo_barrido import verificar_devoluciones
from tests.services.apoyo_bolsas import FECHA_LIMITE, TRES
from tests.services.apoyo_libro import AHORA
from tests.services.apoyo_operaciones_bolsa import (
    FECHA_CORTA,
    SALDO_INICIAL,
    Tx,
    cargar_saldo,
    estado_bolsa,
    estados,
    hacer_aportar,
    hacer_confirmar,
    hacer_retirarse,
    nueva_bolsa,
    saldo_de,
    transacciones,
    usuarios,
)

REPETIR = pytest.mark.parametrize("repeticion", range(10))
BOLSA = "bolsa-ana-cena"


# --- Tareas y ejecución --------------------------------------------------


def envolver(etiqueta, operacion):
    """Tarea que devuelve (etiqueta, ("ok", valor)) o (etiqueta, ("error", codigo))."""

    def tarea(sesion):
        try:
            return etiqueta, ("ok", operacion(sesion))
        except ErrorDominio as error:
            return etiqueta, ("error", error.codigo)

    return tarea


def tarea_aportar(token, bolsa):
    return lambda s: aportar(s, token, uuid4(), bolsa, AHORA)


def tarea_retirarse(token, bolsa):
    return lambda s: retirarse(s, token, uuid4(), bolsa, AHORA)


def tarea_confirmar(token, bolsa):
    return lambda s: confirmar(s, token, bolsa, AHORA)


def tarea_transferir(token, destino, monto):
    return lambda s: transferir(s, token, uuid4(), destino, monto, AHORA)


def tarea_crear(token):
    return lambda s: crear_bolsa(
        s, token, "cena", 90_000, list(TRES), "olga", FECHA_LIMITE, True, AHORA
    )


def a_la_vez(bd, a, b):
    """Corre A y B en dos hilos con barrera; devuelve (resultado A, resultado B)."""
    r = correr_en_hilos(bd, [envolver("A", a), envolver("B", b)], hilos=2)
    assert r.conteo == Counter({"ok": 2})
    por_etiqueta = dict(r.valores)
    ra, rb = por_etiqueta["A"], por_etiqueta["B"]
    for res in (ra, rb):
        assert res != ("error", "reintentos_agotados")
    assert reintentos_por_codigo() == {}
    return ra, rb


# --- Reglas que valen en cualquier orden ---------------------------------


def finales(bd) -> list[Tx]:
    return transacciones(bd, "transferencia_final")


def devoluciones(bd) -> list[Tx]:
    return transacciones(bd, "devolucion")


def sin_devolucion_doble(bd) -> None:
    """A lo sumo una devolución por (bolsa, participante), nunca más de lo aportado."""
    devs = devoluciones(bd)
    pares = Counter((d.origen, d.destino) for d in devs)
    assert all(n == 1 for n in pares.values()), pares
    aportes = Counter()
    for a in transacciones(bd, "aporte"):
        aportes[(a.destino, a.origen)] += a.monto
    for d in devs:
        assert d.monto <= aportes[(d.origen, d.destino)]


def libro_coherente(bd, cuenta_bolsa) -> None:
    """Saldo de la bolsa = aportado − devuelto − transferido, desde el libro."""
    aportado = sum(
        t.monto for t in transacciones(bd, "aporte") if t.destino == cuenta_bolsa
    )
    devuelto = sum(t.monto for t in devoluciones(bd) if t.origen == cuenta_bolsa)
    final = sum(t.monto for t in finales(bd) if t.origen == cuenta_bolsa)
    assert saldo_de(bd, cuenta_bolsa) == aportado - devuelto - final


def reglas_comunes(bd, *cuentas_bolsa) -> None:
    sin_devolucion_doble(bd)
    for cuenta in cuentas_bolsa:
        assert len([f for f in finales(bd) if f.origen == cuenta]) <= 1
        libro_coherente(bd, cuenta)


# --- Filas ---------------------------------------------------------------


@REPETIR
def test_hilos_dos_ultimos_pendientes_aportan(bd, repeticion):
    t = usuarios(bd, "ana", "beto", "carla", "olga")
    bolsa = nueva_bolsa(bd, t)
    hacer_aportar(bd, t["ana"], bolsa)
    ra, rb = a_la_vez(
        bd, tarea_aportar(t["beto"], bolsa), tarea_aportar(t["carla"], bolsa)
    )
    assert ra[0] == rb[0] == "ok"
    reglas_comunes(bd, BOLSA)
    assert finales(bd) == [Tx("transferencia_final", BOLSA, "olga", 90_000)]
    assert estado_bolsa(bd, bolsa) == "cerrada"
    assert set(estados(bd, bolsa).values()) == {"pagado"}
    assert saldo_de(bd, BOLSA) == 0
    assert len(transacciones(bd, "aporte")) == 3


@REPETIR
def test_hilos_ultimo_aporte_contra_el_retiro_de_otro(bd, repeticion):
    t = usuarios(bd, "ana", "beto", "carla", "olga")
    bolsa = nueva_bolsa(bd, t)
    hacer_aportar(bd, t["ana"], bolsa)
    hacer_aportar(bd, t["beto"], bolsa)
    ra, rb = a_la_vez(
        bd, tarea_aportar(t["carla"], bolsa), tarea_retirarse(t["beto"], bolsa)
    )
    reglas_comunes(bd, BOLSA)
    assert ra[0] == "ok"
    if rb == ("error", "estado_invalido"):  # el aporte fue primero
        assert finales(bd) == [Tx("transferencia_final", BOLSA, "olga", 90_000)]
        assert devoluciones(bd) == []
        assert estado_bolsa(bd, bolsa) == "cerrada"
        assert saldo_de(bd, BOLSA) == 0
        assert saldo_de(bd, "beto") == SALDO_INICIAL - 30_000
    else:  # el retiro fue primero
        assert rb[0] == "ok" and rb[1].devolucion.monto == 30_000
        assert devoluciones(bd) == [Tx("devolucion", BOLSA, "beto", 30_000)]
        assert finales(bd) == []
        assert estados(bd, bolsa) == {
            "ana": "por_confirmar",
            "beto": "retirado",
            "carla": "pagado",
        }
        assert estado_bolsa(bd, bolsa) == "abierta"
        assert saldo_de(bd, BOLSA) == 60_000
        assert saldo_de(bd, "beto") == SALDO_INICIAL


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


@REPETIR
def test_hilos_ultima_confirmacion_contra_un_retiro(bd, repeticion):
    t = usuarios(bd, "ana", "beto", "carla", "dani", "olga")
    bolsa = _bolsa_con_dani_retirado(bd, t, ("beto", "carla"))
    ra, rb = a_la_vez(
        bd, tarea_confirmar(t["ana"], bolsa), tarea_retirarse(t["beto"], bolsa)
    )
    reglas_comunes(bd, BOLSA)
    assert ra[0] == "ok"
    if rb == ("error", "estado_invalido"):  # la confirmación fue primero
        assert ra[1].estado_bolsa == "cerrada"
        assert finales(bd) == [Tx("transferencia_final", BOLSA, "olga", 90_000)]
        assert devoluciones(bd) == []  # dani nunca aportó
        assert saldo_de(bd, BOLSA) == 0
    else:  # el retiro fue primero
        assert rb[0] == "ok" and rb[1].devolucion.monto == 30_000
        assert ra[1].estado_bolsa == "abierta"
        assert ra[1].mi_estado == "pagado"
        assert estados(bd, bolsa) == {
            "ana": "pagado",
            "beto": "retirado",
            "carla": "por_confirmar",
            "dani": "retirado",
        }
        assert finales(bd) == []
        assert devoluciones(bd) == [Tx("devolucion", BOLSA, "beto", 30_000)]
        assert saldo_de(bd, BOLSA) == 60_000


@REPETIR
def test_hilos_dos_confirmaciones_finales(bd, repeticion):
    t = usuarios(bd, "ana", "beto", "carla", "dani", "olga")
    bolsa = _bolsa_con_dani_retirado(bd, t, ("carla",))
    ra, rb = a_la_vez(
        bd, tarea_confirmar(t["ana"], bolsa), tarea_confirmar(t["beto"], bolsa)
    )
    reglas_comunes(bd, BOLSA)
    assert ra[0] == rb[0] == "ok"
    assert sorted([ra[1].estado_bolsa, rb[1].estado_bolsa]) == ["abierta", "cerrada"]
    assert finales(bd) == [Tx("transferencia_final", BOLSA, "olga", 90_000)]
    assert estado_bolsa(bd, bolsa) == "cerrada"
    assert saldo_de(bd, BOLSA) == 0


@REPETIR
def test_hilos_retiro_de_los_dos_ultimos_activos(bd, repeticion):
    t = usuarios(bd, "ana", "beto", "carla", "olga")
    bolsa = nueva_bolsa(bd, t)
    hacer_aportar(bd, t["ana"], bolsa)
    hacer_aportar(bd, t["beto"], bolsa)
    hacer_retirarse(bd, t["carla"], bolsa)  # ana y beto en por_confirmar
    ra, rb = a_la_vez(
        bd, tarea_retirarse(t["ana"], bolsa), tarea_retirarse(t["beto"], bolsa)
    )
    reglas_comunes(bd, BOLSA)
    assert ra[0] == rb[0] == "ok"
    assert ra[1].devolucion.monto == rb[1].devolucion.monto == 30_000
    assert len(devoluciones(bd)) == 2
    assert finales(bd) == []
    assert estado_bolsa(bd, bolsa) == "cerrada"
    assert saldo_de(bd, BOLSA) == 0
    assert saldo_de(bd, "ana") == saldo_de(bd, "beto") == SALDO_INICIAL


@REPETIR
def test_hilos_retiro_repetido_con_otra_clave(bd, repeticion):
    t = usuarios(bd, "ana", "beto", "carla", "olga")
    bolsa = nueva_bolsa(bd, t)
    hacer_aportar(bd, t["beto"], bolsa)
    ra, rb = a_la_vez(
        bd, tarea_retirarse(t["beto"], bolsa), tarea_retirarse(t["beto"], bolsa)
    )
    reglas_comunes(bd, BOLSA)
    ok = [r for r in (ra, rb) if r[0] == "ok"]
    assert len(ok) == 1 and ok[0][1].devolucion.monto == 30_000
    assert ("error", "estado_invalido") in (ra, rb)
    assert devoluciones(bd) == [Tx("devolucion", BOLSA, "beto", 30_000)]
    assert saldo_de(bd, "beto") == SALDO_INICIAL
    assert saldo_de(bd, BOLSA) == 0


@REPETIR
def test_hilos_aporte_contra_transferencia_saliente(bd, repeticion):
    t = usuarios(bd, "ana", "beto", "olga")
    t.update(usuarios(bd, "carla", saldo=0))
    cargar_saldo(bd, t["carla"], 40_000)
    bolsa = nueva_bolsa(bd, t)
    ra, rb = a_la_vez(
        bd,
        tarea_aportar(t["carla"], bolsa),
        tarea_transferir(t["carla"], "beto", 20_000),
    )
    reglas_comunes(bd, BOLSA)
    if ra[0] == "ok":
        assert rb == ("error", "saldo_insuficiente")
        assert saldo_de(bd, "carla") == 10_000
        assert saldo_de(bd, BOLSA) == 30_000
        assert saldo_de(bd, "beto") == SALDO_INICIAL
    else:
        assert ra == ("error", "saldo_insuficiente")
        assert rb[0] == "ok"
        assert saldo_de(bd, "carla") == 20_000
        assert saldo_de(bd, BOLSA) == 0
        assert saldo_de(bd, "beto") == SALDO_INICIAL + 20_000


@REPETIR
def test_hilos_aportes_del_mismo_usuario_a_dos_bolsas(bd, repeticion):
    t = usuarios(bd, "ana", "beto", "olga")
    t.update(usuarios(bd, "carla", saldo=0))
    cargar_saldo(bd, t["carla"], 60_000)
    una = nueva_bolsa(bd, t, nombre="una")
    otra = nueva_bolsa(bd, t, creador="beto", nombre="otra")
    ra, rb = a_la_vez(
        bd, tarea_aportar(t["carla"], una), tarea_aportar(t["carla"], otra)
    )
    reglas_comunes(bd, "bolsa-ana-una", "bolsa-beto-otra")
    assert ra[0] == rb[0] == "ok"
    assert saldo_de(bd, "carla") == 0
    assert saldo_de(bd, "bolsa-ana-una") == saldo_de(bd, "bolsa-beto-otra") == 30_000


@REPETIR
def test_hilos_crear_bolsa_contra_transferencia(bd, repeticion):
    t = usuarios(bd, "ana", "beto", "carla", "olga")
    ra, rb = a_la_vez(
        bd, tarea_crear(t["ana"]), tarea_transferir(t["olga"], "ana", 10_000)
    )
    assert ra[0] == rb[0] == "ok"
    assert ra[1].estado == "abierta"
    with bd() as sesion:
        assert sesion.execute(text("SELECT count(*) FROM bolsas")).scalar_one() == 1
    assert saldo_de(bd, "ana") == SALDO_INICIAL + 10_000
    assert saldo_de(bd, "olga") == SALDO_INICIAL - 10_000


# --- Dos barridos a la vez (T14) -----------------------------------------


@REPETIR
def test_dos_barridos_a_la_vez(bd, repeticion):
    """Política de devolver; ana y beto pagaron; la bolsa venció.

    Cada paso relee tras bloquear la bolsa: una sola devolución por
    participante, la bolsa cerrada con saldo 0 y cero reintentos.
    """
    t = usuarios(bd, "ana", "beto", "carla", "olga")
    bolsa = nueva_bolsa(bd, t, transferir_al_vencer=False)
    hacer_aportar(bd, t["ana"], bolsa)
    hacer_aportar(bd, t["beto"], bolsa)
    tareas = [lambda s: procesar_vencidas(bd, FECHA_CORTA) for _ in range(2)]
    res = correr_en_hilos(bd, tareas, hilos=2)
    assert res.conteo == Counter({"ok": 2})
    assert [r.fallidas for r in res.valores] == [[], []]
    assert estado_bolsa(bd, bolsa) == "cerrada"
    assert sorted(transacciones(bd, "devolucion"), key=lambda x: x.destino) == [
        Tx("devolucion", BOLSA, "ana", 30_000),
        Tx("devolucion", BOLSA, "beto", 30_000),
    ]
    assert transacciones(bd, "transferencia_final") == []
    assert {c: saldo_de(bd, c) for c in ("ana", "beto", BOLSA)} == {
        "ana": SALDO_INICIAL,
        "beto": SALDO_INICIAL,
        BOLSA: 0,
    }
    verificar_devoluciones(bd)
    assert reintentos_por_codigo() == {}


@REPETIR
def test_dos_barridos_a_la_vez_con_transferir(bd, repeticion):
    """Política de transferir; ana y beto pagaron, carla pendiente; venció.

    Aquí decide el bloqueo de la bolsa: sin él, los dos barridos verían la
    bolsa en liquidando con saldo y ambos intentarían la transferencia final.
    Exactamente una transferencia de $60.000, ninguna bolsa fallida, la bolsa
    cerrada con saldo 0 y cero reintentos.
    """
    t = usuarios(bd, "ana", "beto", "carla", "olga")
    bolsa = nueva_bolsa(bd, t, transferir_al_vencer=True)
    hacer_aportar(bd, t["ana"], bolsa)
    hacer_aportar(bd, t["beto"], bolsa)
    tareas = [lambda s: procesar_vencidas(bd, FECHA_CORTA) for _ in range(2)]
    res = correr_en_hilos(bd, tareas, hilos=2)
    assert res.conteo == Counter({"ok": 2})
    assert [r.fallidas for r in res.valores] == [[], []]
    assert estado_bolsa(bd, bolsa) == "cerrada"
    assert transacciones(bd, "transferencia_final") == [
        Tx("transferencia_final", BOLSA, "olga", 60_000)
    ]
    assert transacciones(bd, "devolucion") == []
    assert {c: saldo_de(bd, c) for c in ("ana", "beto", "carla", "olga", BOLSA)} == {
        "ana": SALDO_INICIAL - 30_000,
        "beto": SALDO_INICIAL - 30_000,
        "carla": SALDO_INICIAL,
        "olga": SALDO_INICIAL + 60_000,
        BOLSA: 0,
    }
    verificar_devoluciones(bd)
    assert reintentos_por_codigo() == {}
