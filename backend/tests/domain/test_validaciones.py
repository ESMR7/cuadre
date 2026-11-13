"""Validación de monto y de transferencia a uno mismo (SPEC 1.5, 2.1, 5.6)."""

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.domain.constantes import TOPE_OPERACION
from app.domain.errores import ErrorDominio
from app.domain.validaciones import validar_destino_distinto, validar_monto


class EnteroFalso(int):
    """Subclase de int: no es un entero JSON puro."""


def verificar_codigo(excinfo: pytest.ExceptionInfo[BaseException], codigo: str) -> None:
    """Verifica el `codigo`, no solo el tipo (una excepción equivocada falla)."""
    assert isinstance(excinfo.value, ErrorDominio)
    assert excinfo.value.codigo == codigo


def test_tope_es_cincuenta_millones():
    assert TOPE_OPERACION == 50_000_000


@pytest.mark.parametrize("monto", [1, 1000, 49_999_999, 50_000_000])
def test_monto_valido_se_devuelve_identico(monto):
    assert validar_monto(monto) is monto


def test_monto_en_el_tope_pasa():
    assert validar_monto(50_000_000) == 50_000_000


def test_monto_un_peso_sobre_el_tope_es_sobre_el_tope():
    with pytest.raises(ErrorDominio) as excinfo:
        validar_monto(50_000_001)
    verificar_codigo(excinfo, "sobre_el_tope")


def test_monto_cero_es_invalido():
    with pytest.raises(ErrorDominio) as excinfo:
        validar_monto(0)
    verificar_codigo(excinfo, "monto_invalido")


@pytest.mark.parametrize("monto", [-1, -1000, -50_000_000])
def test_monto_negativo_es_invalido(monto):
    with pytest.raises(ErrorDominio) as excinfo:
        validar_monto(monto)
    verificar_codigo(excinfo, "monto_invalido")


@pytest.mark.parametrize("monto", [1000.0, 0.5, float("nan"), float("inf")])
def test_monto_float_se_rechaza_aunque_sea_entero(monto):
    with pytest.raises(ErrorDominio) as excinfo:
        validar_monto(monto)
    verificar_codigo(excinfo, "monto_invalido")


@pytest.mark.parametrize("monto", [True, False])
def test_monto_bool_se_rechaza(monto):
    with pytest.raises(ErrorDominio) as excinfo:
        validar_monto(monto)
    verificar_codigo(excinfo, "monto_invalido")


@pytest.mark.parametrize(
    "monto", ["1000", "", None, Decimal(1000), [1000], EnteroFalso(1000)]
)
def test_monto_de_tipo_no_entero_se_rechaza(monto):
    with pytest.raises(ErrorDominio) as excinfo:
        validar_monto(monto)
    verificar_codigo(excinfo, "monto_invalido")


@given(st.integers(min_value=1, max_value=TOPE_OPERACION))
def test_todo_entero_en_rango_es_valido(monto):
    assert validar_monto(monto) is monto


@given(st.integers(min_value=TOPE_OPERACION + 1))
def test_todo_entero_sobre_el_tope_da_sobre_el_tope(monto):
    with pytest.raises(ErrorDominio) as excinfo:
        validar_monto(monto)
    verificar_codigo(excinfo, "sobre_el_tope")


@given(st.integers(max_value=0))
def test_todo_entero_no_positivo_da_monto_invalido(monto):
    with pytest.raises(ErrorDominio) as excinfo:
        validar_monto(monto)
    verificar_codigo(excinfo, "monto_invalido")


@given(st.floats(allow_nan=True, allow_infinity=True))
def test_ningun_float_es_valido(monto):
    with pytest.raises(ErrorDominio) as excinfo:
        validar_monto(monto)
    verificar_codigo(excinfo, "monto_invalido")


def test_transferencia_a_si_mismo_se_rechaza():
    with pytest.raises(ErrorDominio) as excinfo:
        validar_destino_distinto("ana", "ana")
    verificar_codigo(excinfo, "transferencia_a_si_mismo")


def test_transferencia_a_otra_cuenta_pasa():
    assert validar_destino_distinto("ana", "beto") is None


def test_ids_que_difieren_en_mayusculas_no_se_normalizan():
    # Normalizar a minúsculas es de la API (SPEC 3.3); aquí la comparación es exacta.
    assert validar_destino_distinto("ana", "Ana") is None
