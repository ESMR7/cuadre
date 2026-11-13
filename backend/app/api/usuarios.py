"""POST /usuarios (SPEC 5.2)."""

from fastapi import APIRouter

from app.api.dependencias import Ahora, SesionBD
from app.api.esquemas import Registro, UsuarioSalida
from app.services.usuarios import registrar

router = APIRouter()


@router.post("/usuarios", status_code=201, response_model=UsuarioSalida)
def crear_usuario(datos: Registro, sesion: SesionBD, ahora: Ahora) -> UsuarioSalida:
    usuario = registrar(
        sesion, datos.nombre_usuario, datos.cedula, datos.contrasena, ahora
    )
    return UsuarioSalida(
        nombre_usuario=usuario.nombre_usuario, creado_en=usuario.creado_en
    )
