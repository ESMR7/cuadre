"""Login, autenticación, renovación y logout (SPEC 1.4 y 5.3).

El token en claro solo existe en la respuesta del login; se guarda su SHA-256.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.modelos import Sesion, Usuario
from app.domain.constantes import DURACION_SESION
from app.domain.errores import NoAutenticado
from app.services.seguridad import generar_token, hash_token, verificar_contrasena


@dataclass(frozen=True)
class SesionIniciada:
    token: str
    expira_en: datetime


@dataclass(frozen=True)
class Autenticado:
    usuario_id: int
    cuenta_id: str


def iniciar_sesion(
    sesion_bd: Session, nombre_usuario: str, contrasena: str, ahora: datetime
) -> SesionIniciada:
    """Reemplaza la sesión del usuario por una nueva y devuelve el token.

    Usuario inexistente o contraseña incorrecta: el mismo NoAutenticado.
    """
    with sesion_bd.begin():
        fila = sesion_bd.execute(
            select(Usuario.id, Usuario.contrasena_hash).where(
                Usuario.nombre_usuario == nombre_usuario
            )
        ).one_or_none()
        if fila is None or not verificar_contrasena(contrasena, fila.contrasena_hash):
            raise NoAutenticado()
        token = generar_token()
        expira_en = ahora + DURACION_SESION
        valores = {
            "token_hash": hash_token(token),
            "creada_en": ahora,
            "expira_en": expira_en,
        }
        sesion_bd.execute(
            insert(Sesion)
            .values(usuario_id=fila.id, **valores)
            .on_conflict_do_update(index_elements=[Sesion.usuario_id], set_=valores)
        )
        respuesta = SesionIniciada(token=token, expira_en=expira_en)
    return respuesta


def autenticar(sesion_bd: Session, token: str, ahora: datetime) -> Autenticado:
    """Primer paso de cada caso de uso, dentro de su transacción (SPEC 2.4).

    Lee la sesión sin bloquearla y devuelve solo ids: no carga ninguna Cuenta
    en la sesión de SQLAlchemy. Token inexistente o vencido
    (ahora >= expira_en): NoAutenticado.
    """
    fila = sesion_bd.execute(
        select(Sesion.usuario_id, Usuario.cuenta_id)
        .join(Usuario, Usuario.id == Sesion.usuario_id)
        .where(Sesion.token_hash == hash_token(token), Sesion.expira_en > ahora)
    ).one_or_none()
    if fila is None:
        raise NoAutenticado()
    return Autenticado(usuario_id=fila.usuario_id, cuenta_id=fila.cuenta_id)


def renovar(sesion_bd: Session, token: str, ahora: datetime) -> datetime:
    """Mueve la expiración del token vigente a ahora + 20 minutos.

    Devuelve la nueva expira_en; el token no cambia. Token inexistente o
    vencido (ahora >= expira_en): NoAutenticado, sin cambiar nada.
    """
    expira_en = ahora + DURACION_SESION
    with sesion_bd.begin():
        resultado = sesion_bd.execute(
            update(Sesion)
            .where(Sesion.token_hash == hash_token(token), Sesion.expira_en > ahora)
            .values(expira_en=expira_en)
        )
        if resultado.rowcount != 1:
            raise NoAutenticado()
    return expira_en


def cerrar_sesion(sesion_bd: Session, token: str, ahora: datetime) -> None:
    """Borra la sesión del token vigente. Devuelve None.

    Token inexistente o vencido (ahora >= expira_en): NoAutenticado.
    """
    with sesion_bd.begin():
        resultado = sesion_bd.execute(
            delete(Sesion).where(
                Sesion.token_hash == hash_token(token), Sesion.expira_en > ahora
            )
        )
        if resultado.rowcount != 1:
            raise NoAutenticado()
