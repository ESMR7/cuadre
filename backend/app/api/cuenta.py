"""GET /cuenta y GET /cuenta/movimientos (SPEC 5.7 y 5.8)."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencias import Ahora, SesionBD, Token
from app.api.esquemas import EntradaHistorialSalida, HistorialSalida, SaldoSalida
from app.domain.validaciones import CANTIDAD_MAXIMA, CANTIDAD_POR_DEFECTO
from app.services.consultas import consultar_historial, consultar_saldo

router = APIRouter()


@router.get("/cuenta", response_model=SaldoSalida)
def saldo(token: Token, sesion: SesionBD, ahora: Ahora) -> SaldoSalida:
    resultado = consultar_saldo(sesion, token, ahora)
    return SaldoSalida(cuenta=resultado.cuenta, saldo=resultado.saldo)


@router.get("/cuenta/movimientos", response_model=HistorialSalida)
def historial(
    token: Token,
    sesion: SesionBD,
    ahora: Ahora,
    desde: Annotated[int, Query(ge=0)] = 0,
    cantidad: Annotated[int, Query(ge=1, le=CANTIDAD_MAXIMA)] = CANTIDAD_POR_DEFECTO,
) -> HistorialSalida:
    entradas = consultar_historial(sesion, token, desde, cantidad, ahora)
    return HistorialSalida(
        movimientos=[
            EntradaHistorialSalida(
                tipo=e.tipo,
                contrapartida=e.contrapartida,
                monto=e.monto,
                creado_en=e.creado_en,
            )
            for e in entradas
        ],
        desde=desde,
        cantidad=cantidad,
    )
