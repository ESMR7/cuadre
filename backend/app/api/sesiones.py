"""POST /sesiones, POST /sesiones/renovar y DELETE /sesiones (SPEC 5.3)."""

from fastapi import APIRouter, Response

from app.api.dependencias import Ahora, SesionBD, Token
from app.api.esquemas import Login, RenovacionSalida, SesionSalida
from app.services.sesiones import cerrar_sesion, iniciar_sesion, renovar

router = APIRouter()


@router.post("/sesiones", status_code=201, response_model=SesionSalida)
def entrar(datos: Login, sesion: SesionBD, ahora: Ahora) -> SesionSalida:
    iniciada = iniciar_sesion(sesion, datos.nombre_usuario, datos.contrasena, ahora)
    return SesionSalida(token=iniciada.token, expira_en=iniciada.expira_en)


@router.post("/sesiones/renovar", response_model=RenovacionSalida)
def renovar_sesion(token: Token, sesion: SesionBD, ahora: Ahora) -> RenovacionSalida:
    # Sin parámetro de cuerpo: cualquier cuerpo enviado se ignora (SPEC 9.2).
    return RenovacionSalida(expira_en=renovar(sesion, token, ahora))


@router.delete("/sesiones", status_code=204, response_class=Response)
def salir(token: Token, sesion: SesionBD, ahora: Ahora) -> Response:
    cerrar_sesion(sesion, token, ahora)
    return Response(status_code=204)
