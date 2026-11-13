"""Rutas de bolsas (SPEC 9.2 y 9.4).

Endpoints delgados: validan la forma, reciben `ahora` una vez y delegan en un
solo servicio. El id de la bolsa es un UUID en la ruta: si no lo es, 422
forma_invalida. Aportar, retirarse, confirmar y cancelar no declaran cuerpo,
así que cualquier cuerpo enviado se ignora.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.dependencias import Ahora, Clave, SesionBD, Token
from app.api.dinero import _salida
from app.api.esquemas import (
    BolsaSalida,
    CancelacionSalida,
    ConfirmacionSalida,
    ConteoParticipantesSalida,
    EntradaHistorialSalida,
    HistorialSalida,
    ListaBolsasSalida,
    MiParticipacionSalida,
    NuevaBolsa,
    ResumenBolsaSalida,
    RetiroSalida,
    TransaccionSalida,
)
from app.domain.validaciones import CANTIDAD_MAXIMA, CANTIDAD_POR_DEFECTO
from app.services import operaciones_bolsa
from app.services.bolsas import (
    DetalleBolsa,
    consultar_bolsa,
    crear_bolsa,
    listar_bolsas,
    movimientos_bolsa,
)

router = APIRouter()

Desde = Annotated[int, Query(ge=0)]
Cantidad = Annotated[int, Query(ge=1, le=CANTIDAD_MAXIMA)]


def _detalle(d: DetalleBolsa) -> BolsaSalida:
    p = d.participantes
    return BolsaSalida(
        id=d.id,
        nombre=d.nombre,
        creador=d.creador,
        cuenta_objetivo=d.cuenta_objetivo,
        total=d.total,
        fecha_limite=d.fecha_limite,
        transferir_al_vencer=d.transferir_al_vencer,
        estado=d.estado,
        meta=d.meta,
        aportado=d.aportado,
        transferido=d.transferido,
        participantes=ConteoParticipantesSalida(
            total=p.total,
            pendientes=p.pendientes,
            pagados=p.pagados,
            por_confirmar=p.por_confirmar,
            retirados=p.retirados,
        ),
        mi_participacion=MiParticipacionSalida(
            parte=d.mi_participacion.parte, estado=d.mi_participacion.estado
        ),
    )


@router.post("/bolsas", status_code=201, response_model=BolsaSalida)
def crear(
    datos: NuevaBolsa, token: Token, sesion: SesionBD, ahora: Ahora
) -> BolsaSalida:
    detalle = crear_bolsa(
        sesion,
        token,
        datos.nombre,
        datos.total,
        datos.participantes,
        datos.cuenta_objetivo,
        datos.fecha_limite_utc(),
        datos.transferir_al_vencer,
        ahora,
    )
    return _detalle(detalle)


@router.get("/bolsas", response_model=ListaBolsasSalida)
def listar(
    token: Token,
    sesion: SesionBD,
    ahora: Ahora,
    desde: Desde = 0,
    cantidad: Cantidad = CANTIDAD_POR_DEFECTO,
) -> ListaBolsasSalida:
    resumenes = listar_bolsas(sesion, token, desde, cantidad, ahora)
    return ListaBolsasSalida(
        bolsas=[
            ResumenBolsaSalida(
                id=r.id,
                nombre=r.nombre,
                estado=r.estado,
                fecha_limite=r.fecha_limite,
                mi_parte=r.mi_parte,
                mi_estado=r.mi_estado,
            )
            for r in resumenes
        ],
        desde=desde,
        cantidad=cantidad,
    )


@router.get("/bolsas/{bolsa_id}", response_model=BolsaSalida)
def detalle(
    bolsa_id: UUID, token: Token, sesion: SesionBD, ahora: Ahora
) -> BolsaSalida:
    return _detalle(consultar_bolsa(sesion, token, bolsa_id, ahora))


@router.get("/bolsas/{bolsa_id}/movimientos", response_model=HistorialSalida)
def movimientos(
    bolsa_id: UUID,
    token: Token,
    sesion: SesionBD,
    ahora: Ahora,
    desde: Desde = 0,
    cantidad: Cantidad = CANTIDAD_POR_DEFECTO,
) -> HistorialSalida:
    entradas = movimientos_bolsa(sesion, token, bolsa_id, desde, cantidad, ahora)
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


@router.post(
    "/bolsas/{bolsa_id}/aportes", status_code=201, response_model=TransaccionSalida
)
def aportar(
    bolsa_id: UUID, token: Token, clave: Clave, sesion: SesionBD, ahora: Ahora
) -> TransaccionSalida:
    return _salida(operaciones_bolsa.aportar(sesion, token, clave, bolsa_id, ahora))


@router.post("/bolsas/{bolsa_id}/retiro", response_model=RetiroSalida)
def retirarse(
    bolsa_id: UUID, token: Token, clave: Clave, sesion: SesionBD, ahora: Ahora
) -> RetiroSalida:
    resultado = operaciones_bolsa.retirarse(sesion, token, clave, bolsa_id, ahora)
    devolucion = resultado.devolucion
    return RetiroSalida(devolucion=_salida(devolucion) if devolucion else None)


@router.post("/bolsas/{bolsa_id}/confirmacion", response_model=ConfirmacionSalida)
def confirmar(
    bolsa_id: UUID, token: Token, sesion: SesionBD, ahora: Ahora
) -> ConfirmacionSalida:
    resultado = operaciones_bolsa.confirmar(sesion, token, bolsa_id, ahora)
    return ConfirmacionSalida(
        estado_bolsa=resultado.estado_bolsa, mi_estado=resultado.mi_estado
    )


@router.post("/bolsas/{bolsa_id}/cancelacion", response_model=CancelacionSalida)
def cancelar(
    bolsa_id: UUID, token: Token, sesion: SesionBD, ahora: Ahora
) -> CancelacionSalida:
    resultado = operaciones_bolsa.cancelar(sesion, token, bolsa_id, ahora)
    return CancelacionSalida(estado_bolsa=resultado.estado_bolsa)
