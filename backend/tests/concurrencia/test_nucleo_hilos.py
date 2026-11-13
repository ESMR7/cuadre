"""Filas del núcleo de la tabla 8.4 con hilos (SPEC 10.4).

Cada prueba verifica: (1) el resultado está entre los permitidos; (2) las
reglas que valen en cualquier orden; (3) cero `reintentos_agotados`; (4) cero
reintentos por 40P01. Las invariantes las corre el fixture `bd`, y el fixture
`sin_reintentos` exige además que no haya ningún reintento de ningún código.
Sin sleep: el solapamiento lo da la barrera.
"""

from collections import Counter
from uuid import uuid4

from sqlalchemy import text

from app.services.nucleo import cargar, transferir
from app.services.reintentos import reintentos_por_codigo
from tests.bd_prueba import POOL_PRUEBAS
from tests.concurrencia.apoyo_hilos import correr_en_hilos
from tests.services.apoyo_libro import AHORA, contar, saldo


def hacer_cargar(bd, token, monto):
    with bd() as sesion:
        return cargar(sesion, token, uuid4(), monto, AHORA)


def tarea_cargar(token, monto):
    return lambda sesion: cargar(sesion, token, uuid4(), monto, AHORA)


def tarea_transferir(token, destino, monto, clave=None):
    clave = clave or uuid4()
    return lambda sesion: transferir(sesion, token, clave, destino, monto, AHORA)


def exigir_sin_reintentos(conteo: Counter[str]) -> None:
    assert conteo["reintentos_agotados"] == 0
    assert reintentos_por_codigo().get("40P01", 0) == 0


def transferencias(bd) -> list[int]:
    with bd() as sesion:
        return list(
            sesion.execute(
                text("SELECT monto FROM transacciones WHERE tipo = 'transferencia'")
            ).scalars()
        )


def test_pool_de_pruebas_tiene_al_menos_veinte_conexiones(motor_prueba):
    assert POOL_PRUEBAS >= 20
    assert motor_prueba.pool.size() >= 20


def test_hilos_dos_transferencias_que_superan_saldo(bd, ana, beto):
    hacer_cargar(bd, ana, 100_000)
    r = correr_en_hilos(
        bd, [tarea_transferir(ana, "beto", 60_000) for _ in range(2)], hilos=2
    )
    assert r.conteo == Counter({"ok": 1, "saldo_insuficiente": 1})
    assert saldo(bd, "ana") == 40_000
    assert saldo(bd, "beto") == 60_000
    assert transferencias(bd) == [60_000]
    exigir_sin_reintentos(r.conteo)


def test_hilos_transferencias_cruzadas(bd, ana, beto):
    # 20 en cada sentido con 20 hilos: obliga a que se solapen de verdad.
    hacer_cargar(bd, ana, 100_000)
    hacer_cargar(bd, beto, 100_000)
    tareas = []
    for _ in range(20):
        tareas.append(tarea_transferir(ana, "beto", 1_000))
        tareas.append(tarea_transferir(beto, "ana", 1_000))
    r = correr_en_hilos(bd, tareas, hilos=20)
    assert r.conteo == Counter({"ok": 40})
    assert saldo(bd, "ana") == 100_000
    assert saldo(bd, "beto") == 100_000
    assert len(transferencias(bd)) == 40
    exigir_sin_reintentos(r.conteo)


def test_hilos_misma_clave_mismo_cuerpo(bd, ana, beto):
    hacer_cargar(bd, ana, 100_000)
    clave = uuid4()
    r = correr_en_hilos(
        bd, [tarea_transferir(ana, "beto", 10_000, clave) for _ in range(2)], hilos=2
    )
    assert r.conteo == Counter({"ok": 2})
    assert r.valores[0] == r.valores[1]
    assert transferencias(bd) == [10_000]
    assert saldo(bd, "ana") == 90_000
    assert saldo(bd, "beto") == 10_000
    assert contar(bd, "claves_idempotencia") == 2  # la carga y la transferencia
    exigir_sin_reintentos(r.conteo)


def test_hilos_misma_clave_otro_cuerpo(bd, ana, beto):
    hacer_cargar(bd, ana, 100_000)
    clave = uuid4()
    r = correr_en_hilos(
        bd,
        [
            tarea_transferir(ana, "beto", 10_000, clave),
            tarea_transferir(ana, "beto", 20_000, clave),
        ],
        hilos=2,
    )
    assert r.conteo == Counter({"ok": 1, "clave_reutilizada": 1})
    (ganadora,) = transferencias(bd)
    assert ganadora in (10_000, 20_000)
    assert r.valores[0].monto == ganadora
    assert saldo(bd, "ana") == 100_000 - ganadora
    assert saldo(bd, "ana") in (90_000, 80_000)
    assert saldo(bd, "beto") == ganadora
    with bd() as sesion:
        claves = sesion.execute(
            text("SELECT count(*) FROM claves_idempotencia WHERE clave = :clave"),
            {"clave": clave},
        ).scalar_one()
    assert claves == 1
    exigir_sin_reintentos(r.conteo)


def test_hilos_cien_cargas(bd, ana):
    r = correr_en_hilos(bd, [tarea_cargar(ana, 1_000) for _ in range(100)], hilos=20)
    assert r.conteo == Counter({"ok": 100})
    assert saldo(bd, "ana") == 100_000
    assert saldo(bd, "sistema") == -100_000
    assert contar(bd, "transacciones") == 100
    exigir_sin_reintentos(r.conteo)


def test_hilos_cien_transferencias(bd, ana, beto):
    hacer_cargar(bd, ana, 1_000_000)
    r = correr_en_hilos(
        bd, [tarea_transferir(ana, "beto", 20_000) for _ in range(100)], hilos=20
    )
    assert r.conteo == Counter({"ok": 50, "saldo_insuficiente": 50})
    assert saldo(bd, "ana") == 0
    assert saldo(bd, "beto") == 1_000_000
    assert transferencias(bd) == [20_000] * 50
    exigir_sin_reintentos(r.conteo)
