"""POST /cargas y POST /transferencias (SPEC 5.4 y 5.5).

Un reintento con la misma clave devuelve el mismo 201 y el mismo cuerpo: el
servicio reconstruye la transacción original desde el libro.
"""

from fastapi import APIRouter

from app.api.dependencias import Ahora, Clave, SesionBD, Token
from app.api.esquemas import Carga, TransaccionSalida, Transferencia
from app.services.libro import TransaccionRegistrada
from app.services.nucleo import cargar, transferir

router = APIRouter()


def _salida(t: TransaccionRegistrada) -> TransaccionSalida:
    return TransaccionSalida(
        id=t.id,
        tipo=t.tipo,
        origen=t.origen,
        destino=t.destino,
        monto=t.monto,
        creado_en=t.creado_en,
    )


@router.post("/cargas", status_code=201, response_model=TransaccionSalida)
def crear_carga(
    datos: Carga, token: Token, clave: Clave, sesion: SesionBD, ahora: Ahora
) -> TransaccionSalida:
    return _salida(cargar(sesion, token, clave, datos.monto, ahora))


@router.post("/transferencias", status_code=201, response_model=TransaccionSalida)
def crear_transferencia(
    datos: Transferencia, token: Token, clave: Clave, sesion: SesionBD, ahora: Ahora
) -> TransaccionSalida:
    return _salida(transferir(sesion, token, clave, datos.destino, datos.monto, ahora))
