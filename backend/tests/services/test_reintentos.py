"""Envoltorio de reintentos (SPEC 2.3). Sin base: errores reales de psycopg."""

import logging

import psycopg.errors
import pytest
from sqlalchemy.exc import OperationalError

from app.domain.errores import ReintentosAgotados, SaldoInsuficiente
from app.services.reintentos import (
    INTENTOS_MAXIMOS,
    ejecutar_con_reintentos,
    reiniciar_contador,
    reintentos_por_codigo,
)


def error_sql(clase: type[psycopg.Error], mensaje: str = "x") -> OperationalError:
    return OperationalError("SELECT 1", {}, clase(mensaje))


class Funcion:
    """Lanza los errores dados en orden y después devuelve 'ok'."""

    def __init__(self, *errores: Exception) -> None:
        self.errores = list(errores)
        self.llamadas = 0

    def __call__(self) -> str:
        self.llamadas += 1
        if self.errores:
            raise self.errores.pop(0)
        return "ok"


@pytest.fixture(autouse=True)
def contador_limpio():
    reiniciar_contador()
    yield
    reiniciar_contador()


def test_intentos_maximos_son_3():
    assert INTENTOS_MAXIMOS == 3


def test_reintenta_40P01_y_40001_y_devuelve_resultado():
    funcion = Funcion(
        error_sql(psycopg.errors.DeadlockDetected),
        error_sql(psycopg.errors.SerializationFailure),
    )
    assert ejecutar_con_reintentos("cargar", funcion) == "ok"
    assert funcion.llamadas == 3
    assert reintentos_por_codigo() == {"40P01": 1, "40001": 1}


def test_agota_reintentos_y_lanza_reintentos_agotados():
    funcion = Funcion(*[error_sql(psycopg.errors.DeadlockDetected) for _ in range(5)])
    with pytest.raises(ReintentosAgotados):
        ejecutar_con_reintentos("cargar", funcion)
    assert funcion.llamadas == 3


def test_identifica_por_sqlstate_y_no_por_el_mensaje():
    # El mensaje dice "deadlock" pero el código es de unicidad: no se reintenta.
    funcion = Funcion(
        error_sql(psycopg.errors.UniqueViolation, "deadlock detected 40P01")
    )
    with pytest.raises(OperationalError):
        ejecutar_con_reintentos("cargar", funcion)
    assert funcion.llamadas == 1
    assert reintentos_por_codigo() == {}


def test_no_reintenta_error_de_dominio():
    funcion = Funcion(SaldoInsuficiente())
    with pytest.raises(SaldoInsuficiente):
        ejecutar_con_reintentos("transferir", funcion)
    assert funcion.llamadas == 1
    assert reintentos_por_codigo() == {}


def test_contador_por_codigo_se_lee_y_se_reinicia():
    ejecutar_con_reintentos(
        "cargar", Funcion(error_sql(psycopg.errors.DeadlockDetected))
    )
    assert reintentos_por_codigo() == {"40P01": 1}
    copia = reintentos_por_codigo()
    copia["40P01"] = 99
    assert reintentos_por_codigo() == {"40P01": 1}
    reiniciar_contador()
    assert reintentos_por_codigo() == {}


def test_cada_reintento_queda_en_el_log_con_caso_codigo_e_intento(caplog):
    secreto = "detalle-con-datos-sensibles"
    funcion = Funcion(
        error_sql(psycopg.errors.DeadlockDetected, secreto),
        error_sql(psycopg.errors.DeadlockDetected, secreto),
    )
    with caplog.at_level(logging.WARNING, logger="app.services.reintentos"):
        ejecutar_con_reintentos("transferir", funcion)
    registros = [r for r in caplog.records if r.name == "app.services.reintentos"]
    assert len(registros) == 2
    for numero, registro in enumerate(registros, start=1):
        texto = registro.getMessage()
        assert "transferir" in texto
        assert "40P01" in texto
        assert str(numero) in texto
        assert secreto not in texto
