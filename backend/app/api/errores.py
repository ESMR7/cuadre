"""Traducción de errores a HTTP (SPEC 2.6 y 9.1).

`HTTP_POR_CODIGO` es el único lugar con la tabla de `codigo` a HTTP. Todo error
sale como {"codigo", "mensaje"} y, en `forma_invalida`, además "campos".

Ningún mensaje copia datos de la petición (la entrada de Pydantic puede traer
la contraseña o la cédula) ni de una excepción inesperada (puede traer la URL
de la base).
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.errores import ErrorDominio

logger = logging.getLogger("cuadre.api")

HTTP_POR_CODIGO: dict[str, int] = {
    "forma_invalida": 422,
    "monto_invalido": 422,
    "sobre_el_tope": 422,
    "transferencia_a_si_mismo": 422,
    "total_invalido": 422,
    "fecha_limite_invalida": 422,
    "participantes_invalidos": 422,
    "falta_clave_idempotencia": 400,
    "no_autenticado": 401,
    "sin_permiso": 403,
    "no_encontrado": 404,
    "registro_rechazado": 409,
    "nombre_en_uso": 409,
    "saldo_insuficiente": 409,
    "fuera_de_plazo": 409,
    "estado_invalido": 409,
    "clave_reutilizada": 409,
    "metodo_no_permitido": 405,
    "reintentos_agotados": 503,
    "error_interno": 500,
}

MENSAJE_FORMA_INVALIDA = "La petición tiene una forma inválida."
MENSAJE_ERROR_INTERNO = "Error interno."
MENSAJE_RUTA_INEXISTENTE = "La ruta no existe."
MENSAJE_METODO = "Método no permitido en la ruta."


def respuesta_error(
    codigo: str,
    mensaje: str,
    campos: list[str] | None = None,
    cabeceras: dict[str, str] | None = None,
) -> JSONResponse:
    cuerpo: dict[str, object] = {"codigo": codigo, "mensaje": mensaje}
    if codigo == "forma_invalida":
        cuerpo["campos"] = campos or []
    return JSONResponse(cuerpo, status_code=HTTP_POR_CODIGO[codigo], headers=cabeceras)


def _nombre_campo(ubicacion: tuple) -> str:
    """Último nombre de texto de la ubicación; 'cuerpo' si no hay ninguno."""
    nombres = [p for p in ubicacion[1:] if isinstance(p, str)]
    return nombres[-1] if nombres else "cuerpo"


def _error_dominio(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ErrorDominio)
    if exc.codigo not in HTTP_POR_CODIGO:
        return _error_inesperado(_, exc)
    return respuesta_error(exc.codigo, exc.mensaje)


def _error_validacion(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    campos: list[str] = []
    for detalle in exc.errors():
        nombre = _nombre_campo(tuple(detalle.get("loc", ())))
        if nombre not in campos:
            campos.append(nombre)
    return respuesta_error("forma_invalida", MENSAJE_FORMA_INVALIDA, campos)


def _error_http(peticion: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    if exc.status_code == 404:
        return respuesta_error("no_encontrado", MENSAJE_RUTA_INEXISTENTE)
    if exc.status_code == 405:
        return respuesta_error(
            "metodo_no_permitido", MENSAJE_METODO, cabeceras=exc.headers
        )
    return _error_inesperado(peticion, exc)


def _error_inesperado(peticion: Request, exc: Exception) -> JSONResponse:
    # Sin exc_info ni str(exc): el traceback y el mensaje pueden traer la URL
    # de la base u otros datos sensibles.
    logger.error(
        "Error inesperado %s en %s %s",
        type(exc).__name__,
        peticion.method,
        peticion.url.path,
    )
    return respuesta_error("error_interno", MENSAJE_ERROR_INTERNO)


def registrar_manejadores(app: FastAPI) -> None:
    app.add_exception_handler(ErrorDominio, _error_dominio)
    app.add_exception_handler(RequestValidationError, _error_validacion)
    app.add_exception_handler(StarletteHTTPException, _error_http)
    app.add_exception_handler(Exception, _error_inesperado)
