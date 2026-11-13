"""Catálogo de errores de dominio contra la tabla de SPEC 2.6."""

import inspect

from app.domain import errores
from app.domain.errores import ErrorDominio, MontoInvalido

# Copiado de la tabla de SPEC 2.6, columna `codigo` (19 filas).
CODIGOS_SPEC_2_6 = {
    "forma_invalida",
    "monto_invalido",
    "sobre_el_tope",
    "transferencia_a_si_mismo",
    "total_invalido",
    "fecha_limite_invalida",
    "participantes_invalidos",
    "falta_clave_idempotencia",
    "no_autenticado",
    "sin_permiso",
    "no_encontrado",
    "registro_rechazado",
    "nombre_en_uso",
    "saldo_insuficiente",
    "fuera_de_plazo",
    "estado_invalido",
    "clave_reutilizada",
    "metodo_no_permitido",
    "reintentos_agotados",
}


def _clases_de_error() -> list[type[ErrorDominio]]:
    return [
        c
        for _, c in inspect.getmembers(errores, inspect.isclass)
        if issubclass(c, ErrorDominio) and c is not ErrorDominio
    ]


def test_codigos_coinciden_con_spec():
    codigos = [c.codigo for c in _clases_de_error()]
    assert set(codigos) == CODIGOS_SPEC_2_6


def test_cada_error_tiene_codigo_unico():
    codigos = [c.codigo for c in _clases_de_error()]
    assert len(codigos) == len(set(codigos)) == len(CODIGOS_SPEC_2_6)


def test_error_conserva_mensaje_y_es_error_dominio():
    error = MontoInvalido("monto malo")
    assert isinstance(error, ErrorDominio)
    assert error.mensaje == "monto malo"
    assert error.codigo == "monto_invalido"


def test_error_sin_mensaje_usa_el_de_por_defecto():
    assert MontoInvalido().mensaje
