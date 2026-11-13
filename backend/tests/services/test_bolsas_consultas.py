"""Consultar bolsas: detalle, mis bolsas y mis movimientos (SPEC 9.4, T10)."""

import dataclasses
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text

import app.services.bolsas as servicio
from app.domain.errores import ErrorDominio
from app.services.bolsas import (
    ConteoParticipantes,
    MiParticipacion,
    consultar_bolsa,
    listar_bolsas,
    movimientos_bolsa,
)
from app.services.nucleo import cargar, transferir
from tests.services.apoyo_bolsas import conteos, crear
from tests.services.apoyo_libro import AHORA, crear_usuario


@pytest.fixture
def tokens(bd) -> dict[str, str]:
    nombres = ("ana", "beto", "carla", "olga", "zoe")
    return {n: crear_usuario(bd, n, f"200000{i}") for i, n in enumerate(nombres)}


def verificar_codigo(excinfo, codigo: str) -> None:
    assert isinstance(excinfo.value, ErrorDominio)
    assert excinfo.value.codigo == codigo


def detalle(bd, token, bolsa_id):
    with bd() as sesion:
        return consultar_bolsa(sesion, token, bolsa_id, AHORA)


def listar(bd, token, desde=0, cantidad=20):
    with bd() as sesion:
        return listar_bolsas(sesion, token, desde, cantidad, AHORA)


def movimientos(bd, token, bolsa_id, desde=0, cantidad=20):
    with bd() as sesion:
        return movimientos_bolsa(sesion, token, bolsa_id, desde, cantidad, AHORA)


# --- Detalle -----------------------------------------------------------------


def test_detalle_coincide_con_lo_que_devuelve_crear(bd, tokens):
    creado = crear(bd, tokens["ana"])
    assert detalle(bd, tokens["ana"], creado.id) == creado


def test_cada_participante_ve_solo_su_participacion(bd, tokens):
    creado = crear(bd, tokens["beto"], total=100_000)
    vistas = {n: detalle(bd, tokens[n], creado.id) for n in ("ana", "beto", "carla")}
    assert vistas["ana"].mi_participacion == MiParticipacion(33_333, "pendiente")
    assert vistas["beto"].mi_participacion == MiParticipacion(33_334, "pendiente")
    assert vistas["carla"].mi_participacion == MiParticipacion(33_333, "pendiente")
    for vista in vistas.values():
        assert vista.participantes == ConteoParticipantes(3, 3, 0, 0, 0)
        # Solo términos, totales y lo propio: nada de otros participantes.
        sin_mia = dataclasses.replace(
            vista, mi_participacion=vistas["ana"].mi_participacion
        )
        assert sin_mia == vistas["ana"]
    campos = {f.name for f in dataclasses.fields(vistas["ana"])}
    assert campos == {
        "id",
        "nombre",
        "creador",
        "cuenta_objetivo",
        "total",
        "fecha_limite",
        "transferir_al_vencer",
        "estado",
        "meta",
        "aportado",
        "transferido",
        "participantes",
        "mi_participacion",
    }


def test_detalle_no_participante_da_sin_permiso(bd, tokens):
    creado = crear(bd, tokens["ana"])
    with pytest.raises(ErrorDominio) as exc:
        detalle(bd, tokens["olga"], creado.id)
    verificar_codigo(exc, "sin_permiso")


def test_detalle_bolsa_inexistente_da_no_encontrado(bd, tokens):
    with pytest.raises(ErrorDominio) as exc:
        detalle(bd, tokens["ana"], uuid4())
    verificar_codigo(exc, "no_encontrado")


def test_detalle_sin_sesion_da_no_autenticado(bd, tokens):
    creado = crear(bd, tokens["ana"])
    with pytest.raises(ErrorDominio) as exc:
        detalle(bd, "token-inexistente", creado.id)
    verificar_codigo(exc, "no_autenticado")


# --- Aislamiento -------------------------------------------------------------


def _registrar_aislamiento(monkeypatch) -> list[tuple[str, str]]:
    """Reemplaza `_bolsa_visible` por una envoltura que lee el nivel real."""
    vistos: list[tuple[str, str]] = []
    original = servicio._bolsa_visible

    def envoltura(sesion, *args, **kwargs):
        fila = sesion.execute(
            text(
                "SELECT current_setting('transaction_isolation'), "
                "current_setting('transaction_read_only')"
            )
        ).one()
        vistos.append((fila[0], fila[1]))
        return original(sesion, *args, **kwargs)

    monkeypatch.setattr(servicio, "_bolsa_visible", envoltura)
    return vistos


def test_detalle_lee_en_repeatable_read_solo_lectura(bd, tokens, monkeypatch):
    creado = crear(bd, tokens["ana"])
    vistos = _registrar_aislamiento(monkeypatch)
    detalle(bd, tokens["ana"], creado.id)
    assert vistos == [("repeatable read", "on")]


def test_movimientos_leen_en_repeatable_read_solo_lectura(bd, tokens, monkeypatch):
    creado = crear(bd, tokens["ana"])
    vistos = _registrar_aislamiento(monkeypatch)
    movimientos(bd, tokens["ana"], creado.id)
    assert vistos == [("repeatable read", "on")]


# --- Mis bolsas --------------------------------------------------------------


def test_listar_de_la_mas_reciente_a_la_mas_antigua(bd, tokens):
    for i, nombre in enumerate(("primera", "segunda", "tercera")):
        crear(bd, tokens["ana"], nombre=nombre, ahora=AHORA + timedelta(minutes=i))
    resumen = listar(bd, tokens["ana"])
    assert [r.nombre for r in resumen] == ["tercera", "segunda", "primera"]
    assert all(r.mi_parte == 30_000 and r.mi_estado == "pendiente" for r in resumen)
    assert all(r.estado == "abierta" for r in resumen)


def test_listar_solo_incluye_mis_bolsas(bd, tokens):
    crear(
        bd,
        tokens["ana"],
        nombre="con_beto",
        participantes=("ana", "beto"),
        total=60_000,
    )
    crear(
        bd,
        tokens["carla"],
        nombre="sin_beto",
        participantes=("carla", "olga"),
        total=60_000,
    )
    assert [r.nombre for r in listar(bd, tokens["beto"])] == ["con_beto"]
    assert listar(bd, tokens["zoe"]) == []


def test_listar_pagina_con_desde_y_cantidad(bd, tokens):
    for i in range(5):
        crear(bd, tokens["ana"], nombre=f"b{i}", ahora=AHORA + timedelta(minutes=i))
    pagina = listar(bd, tokens["ana"], desde=1, cantidad=2)
    assert [r.nombre for r in pagina] == ["b3", "b2"]


@pytest.mark.parametrize(("desde", "cantidad"), [(-1, 20), (0, 0), (0, 101)])
def test_listar_paginacion_invalida_da_forma_invalida(bd, tokens, desde, cantidad):
    with pytest.raises(ErrorDominio) as exc:
        listar(bd, tokens["ana"], desde, cantidad)
    verificar_codigo(exc, "forma_invalida")


# --- Mis movimientos con la bolsa --------------------------------------------


def test_movimientos_de_bolsa_recien_creada_estan_vacios(bd, tokens):
    creado = crear(bd, tokens["ana"])
    assert movimientos(bd, tokens["ana"], creado.id) == []


def test_movimientos_excluyen_mis_transferencias_ajenas_a_la_bolsa(bd, tokens):
    creado = crear(bd, tokens["ana"])
    with bd() as sesion:
        cargar(sesion, tokens["ana"], uuid4(), 50_000, AHORA)
    with bd() as sesion:
        transferir(sesion, tokens["ana"], uuid4(), "beto", 10_000, AHORA)
    assert movimientos(bd, tokens["ana"], creado.id) == []
    assert movimientos(bd, tokens["beto"], creado.id) == []


def test_movimientos_no_participante_da_sin_permiso(bd, tokens):
    creado = crear(bd, tokens["ana"])
    with pytest.raises(ErrorDominio) as exc:
        movimientos(bd, tokens["olga"], creado.id)
    verificar_codigo(exc, "sin_permiso")


def test_movimientos_bolsa_inexistente_da_no_encontrado(bd, tokens):
    with pytest.raises(ErrorDominio) as exc:
        movimientos(bd, tokens["ana"], uuid4())
    verificar_codigo(exc, "no_encontrado")


def test_movimientos_paginacion_invalida_da_forma_invalida(bd, tokens):
    creado = crear(bd, tokens["ana"])
    with pytest.raises(ErrorDominio) as exc:
        movimientos(bd, tokens["ana"], creado.id, cantidad=0)
    verificar_codigo(exc, "forma_invalida")


# --- Solo lectura ------------------------------------------------------------


def test_consultas_no_escriben(bd, tokens):
    creado = crear(bd, tokens["ana"])
    antes = conteos(bd)
    detalle(bd, tokens["beto"], creado.id)
    listar(bd, tokens["beto"])
    movimientos(bd, tokens["beto"], creado.id)
    assert conteos(bd) == antes
