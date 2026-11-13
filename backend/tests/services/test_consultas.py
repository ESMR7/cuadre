"""Saldo e historial (SPEC 5.7 y 5.8, T7)."""

import dataclasses
from datetime import timedelta
from uuid import uuid4

import pytest

from app.domain.errores import FormaInvalida, NoAutenticado
from app.services.consultas import (
    EntradaHistorial,
    SaldoCuenta,
    consultar_historial,
    consultar_saldo,
)
from app.services.nucleo import cargar, transferir
from tests.services.apoyo_libro import AHORA, capturar_sql, crear_usuario

BLOQUEOS = ("FOR UPDATE", "FOR NO KEY UPDATE", "FOR SHARE", "FOR KEY SHARE")


@pytest.fixture
def ana(bd) -> str:
    return crear_usuario(bd, "ana", "1000001")


@pytest.fixture
def beto(bd) -> str:
    return crear_usuario(bd, "beto", "1000002")


def hacer_cargar(bd, token, monto, ahora=AHORA):
    with bd() as sesion:
        return cargar(sesion, token, uuid4(), monto, ahora)


def hacer_transferir(bd, token, destino, monto, ahora=AHORA):
    with bd() as sesion:
        return transferir(sesion, token, uuid4(), destino, monto, ahora)


def leer_saldo(bd, token) -> SaldoCuenta:
    with bd() as sesion:
        return consultar_saldo(sesion, token, AHORA)


def leer_historial(bd, token, desde=0, cantidad=20) -> list[EntradaHistorial]:
    with bd() as sesion:
        return consultar_historial(sesion, token, desde, cantidad, AHORA)


def exigir_lectura_sin_bloqueo(sentencias) -> None:
    textos = [sentencia.upper() for sentencia, _ in sentencias]
    assert any("SET TRANSACTION READ ONLY" in t for t in textos)
    for texto in textos:
        assert not any(bloqueo in texto for bloqueo in BLOQUEOS), texto


# --- Saldo ------------------------------------------------------------------


def test_saldo_devuelve_saldo_de_la_cuenta_propia(bd, ana, beto):
    hacer_cargar(bd, ana, 100_000)
    hacer_cargar(bd, ana, 50_000)
    hacer_transferir(bd, ana, "beto", 30_000)
    assert leer_saldo(bd, ana) == SaldoCuenta(cuenta="ana", saldo=120_000)
    assert leer_saldo(bd, beto) == SaldoCuenta(cuenta="beto", saldo=30_000)


def test_saldo_cuenta_nueva_es_cero(bd, ana):
    assert leer_saldo(bd, ana) == SaldoCuenta(cuenta="ana", saldo=0)


def test_saldo_usa_transaccion_de_solo_lectura_sin_bloqueo(bd, motor_prueba, ana):
    hacer_cargar(bd, ana, 10_000)
    with capturar_sql(motor_prueba) as sentencias:
        leer_saldo(bd, ana)
    exigir_lectura_sin_bloqueo(sentencias)


def test_saldo_token_invalido_da_no_autenticado(bd, ana):
    with pytest.raises(NoAutenticado):
        leer_saldo(bd, "token-que-no-existe")


# --- Historial --------------------------------------------------------------


def test_historial_muestra_tipo_contrapartida_monto_con_signo_y_fecha(bd, ana, beto):
    t1 = AHORA
    t2 = AHORA + timedelta(minutes=1)
    hacer_cargar(bd, ana, 100_000, t1)
    hacer_transferir(bd, ana, "beto", 20_000, t2)
    assert leer_historial(bd, ana) == [
        EntradaHistorial("transferencia", "beto", -20_000, t2),
        EntradaHistorial("carga", "sistema", 100_000, t1),
    ]
    assert leer_historial(bd, beto) == [
        EntradaHistorial("transferencia", "ana", 20_000, t2),
    ]


def test_historial_ordena_por_fecha_descendente(bd, ana):
    # Se insertan en orden inverso a la fecha: el id no decide el orden.
    hacer_cargar(bd, ana, 3_000, AHORA + timedelta(minutes=3))
    hacer_cargar(bd, ana, 1_000, AHORA + timedelta(minutes=1))
    hacer_cargar(bd, ana, 2_000, AHORA + timedelta(minutes=2))
    assert [e.monto for e in leer_historial(bd, ana)] == [3_000, 2_000, 1_000]


def test_historial_desempata_por_id_de_transaccion_descendente(bd, ana, beto):
    hacer_cargar(bd, ana, 100_000, AHORA - timedelta(minutes=1))
    for monto in (1_000, 2_000, 3_000):
        hacer_transferir(bd, ana, "beto", monto, AHORA)
    montos = [e.monto for e in leer_historial(bd, ana)]
    assert montos == [-3_000, -2_000, -1_000, 100_000]


def test_historial_pagina_con_desde_y_cantidad(bd, ana):
    for i in range(1, 6):
        hacer_cargar(bd, ana, i * 1_000, AHORA + timedelta(minutes=i))
    paginas = [leer_historial(bd, ana, desde, 2) for desde in (0, 2, 4)]
    assert [[e.monto for e in p] for p in paginas] == [
        [5_000, 4_000],
        [3_000, 2_000],
        [1_000],
    ]


def test_historial_desde_mas_alla_del_final_devuelve_lista_vacia(bd, ana):
    hacer_cargar(bd, ana, 1_000)
    assert leer_historial(bd, ana, desde=1, cantidad=20) == []


def test_historial_cuenta_nueva_esta_vacio(bd, ana):
    assert leer_historial(bd, ana) == []


def test_historial_solo_incluye_la_cuenta_propia(bd, ana, beto):
    hacer_cargar(bd, ana, 10_000)
    hacer_cargar(bd, beto, 7_000)
    assert leer_historial(bd, ana) == [
        EntradaHistorial("carga", "sistema", 10_000, AHORA)
    ]


def test_entrada_historial_no_expone_id_ni_saldo():
    campos = {c.name for c in dataclasses.fields(EntradaHistorial)}
    assert campos == {"tipo", "contrapartida", "monto", "creado_en"}


@pytest.mark.parametrize(("desde", "cantidad"), [(-1, 20), (0, 0), (0, 101)])
def test_historial_paginacion_invalida_da_forma_invalida(bd, ana, desde, cantidad):
    with pytest.raises(FormaInvalida) as excinfo:
        leer_historial(bd, ana, desde, cantidad)
    assert excinfo.value.codigo == "forma_invalida"


def test_historial_token_invalido_da_no_autenticado(bd, ana):
    with pytest.raises(NoAutenticado):
        leer_historial(bd, "token-que-no-existe")


def test_historial_usa_transaccion_de_solo_lectura_sin_bloqueo(bd, motor_prueba, ana):
    hacer_cargar(bd, ana, 10_000)
    with capturar_sql(motor_prueba) as sentencias:
        leer_historial(bd, ana)
    exigir_lectura_sin_bloqueo(sentencias)
