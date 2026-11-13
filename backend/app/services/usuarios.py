"""Registro de usuarios (SPEC 5.2)."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.modelos import Cuenta, Usuario
from app.domain.errores import RegistroRechazado
from app.services.seguridad import hashear_contrasena, parametros_configurados

# Restricciones que significan "nombre o cédula ya registrados". Un nombre
# repetido choca primero con pk_cuentas, porque la cuenta se inserta antes.
RESTRICCIONES_DE_REGISTRO = frozenset(
    {"pk_cuentas", "uq_usuarios_nombre", "uq_usuarios_cedula", "uq_usuarios_cuenta"}
)


@dataclass(frozen=True)
class UsuarioRegistrado:
    nombre_usuario: str
    creado_en: datetime


def _restriccion(error: IntegrityError) -> str | None:
    diagnostico = getattr(error.orig, "diag", None)
    return getattr(diagnostico, "constraint_name", None)


def registrar(
    sesion_bd: Session,
    nombre_usuario: str,
    cedula: str,
    contrasena: str,
    ahora: datetime,
) -> UsuarioRegistrado:
    """Crea la cuenta personal y el usuario en una sola transacción.

    Recibe datos ya validados y normalizados por la API. Nombre o cédula
    repetidos: RegistroRechazado. Cualquier otra violación se propaga.
    """
    # scrypt es lento: se calcula antes de abrir la transacción.
    contrasena_hash = hashear_contrasena(contrasena, parametros_configurados())
    try:
        with sesion_bd.begin():
            sesion_bd.add(
                Cuenta(id=nombre_usuario, tipo="personal", saldo=0, creada_en=ahora)
            )
            sesion_bd.flush()
            sesion_bd.add(
                Usuario(
                    cedula=cedula,
                    nombre_usuario=nombre_usuario,
                    contrasena_hash=contrasena_hash,
                    cuenta_id=nombre_usuario,
                    creado_en=ahora,
                )
            )
            sesion_bd.flush()
            respuesta = UsuarioRegistrado(
                nombre_usuario=nombre_usuario, creado_en=ahora
            )
    except IntegrityError as error:
        if _restriccion(error) in RESTRICCIONES_DE_REGISTRO:
            # from None: el DETAIL de PostgreSQL incluye la cédula.
            raise RegistroRechazado() from None
        raise
    return respuesta
