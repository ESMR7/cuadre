"""Datos de demo: `python -m app.seed` o `make seed` (T16).

Usa solo los servicios, nunca SQL directo, para que las invariantes se sigan
cumpliendo. Se puede correr varias veces: los usuarios y bolsas que ya existen
se reportan y se saltan, y las cargas y los aportes usan claves de
idempotencia fijas, así que repetirlos devuelve el resultado original sin
mover dinero. Si una corrida quedó a medias, la siguiente la completa.

Nunca imprime cédulas, tokens, contraseñas, la URL de la base ni el texto de
una excepción. Vive fuera de `services/` porque lee el reloj.
"""

import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from app.db.sesion import crear_fabrica, obtener_motor
from app.domain.errores import (
    EstadoInvalido,
    FueraDePlazo,
    NombreEnUso,
    RegistroRechazado,
)
from app.services import bolsas, nucleo, operaciones_bolsa, sesiones, usuarios

CONTRASENA_DEMO = "demo-cuadre-2026"
MONTO_CARGA = 200_000

# Cédulas ficticias, solo para la demo.
USUARIOS = {
    "ana": "1000000001",
    "beto": "1000000002",
    "carla": "1000000003",
    "olga": "1000000004",
}

# Claves de idempotencia fijas (UUID v4): repetir el seed no repite dinero.
CLAVES_CARGA = {
    "ana": UUID("3f0c6a1e-5b7d-4c2a-9e81-0a1b2c3d4e01"),
    "beto": UUID("3f0c6a1e-5b7d-4c2a-9e81-0a1b2c3d4e02"),
    "carla": UUID("3f0c6a1e-5b7d-4c2a-9e81-0a1b2c3d4e03"),
}
CLAVE_APORTE_CENA = UUID("7a4d2b9c-1e3f-4a5b-8c6d-0e1f2a3b4c01")
CLAVE_APORTE_VENCE = UUID("7a4d2b9c-1e3f-4a5b-8c6d-0e1f2a3b4c02")


def _reloj() -> datetime:
    return datetime.now(UTC)


def _registrar(sesion: Session, ahora: datetime) -> list[str]:
    existentes = []
    for nombre, cedula in USUARIOS.items():
        try:
            usuarios.registrar(sesion, nombre, cedula, CONTRASENA_DEMO, ahora)
            print(f"Usuario {nombre} creado.")
        except RegistroRechazado:
            print(f"El usuario {nombre} ya existe; se deja como está.")
            existentes.append(nombre)
    return existentes


def _buscar_bolsa(sesion: Session, token: str, nombre: str, ahora: datetime) -> UUID:
    for resumen in bolsas.listar_bolsas(sesion, token, 0, 100, ahora):
        if resumen.nombre == nombre:
            return resumen.id
    raise LookupError(nombre)


def _bolsa(
    sesion: Session,
    token_creador: str,
    nombre: str,
    total: int,
    participantes: list[str],
    fecha_limite: datetime,
    transferir_al_vencer: bool,
    ahora: datetime,
) -> tuple[UUID, bool]:
    """Crea la bolsa o encuentra la existente. Devuelve (id, ya_existia)."""
    try:
        detalle = bolsas.crear_bolsa(
            sesion,
            token_creador,
            nombre,
            total,
            participantes,
            "olga",
            fecha_limite,
            transferir_al_vencer,
            ahora,
        )
        print(f"Bolsa {nombre} creada.")
        return detalle.id, False
    except NombreEnUso:
        print(f"La bolsa {nombre} ya existe; se deja como está.")
        return _buscar_bolsa(sesion, token_creador, nombre, ahora), True


def _aportar(
    sesion: Session,
    token: str,
    quien: str,
    clave: UUID,
    bolsa_id: UUID,
    nombre: str,
    ahora: datetime,
) -> None:
    try:
        operaciones_bolsa.aportar(sesion, token, clave, bolsa_id, ahora)
        print(f"Aporte de {quien} a {nombre} listo.")
    except (FueraDePlazo, EstadoInvalido):
        print(f"La bolsa {nombre} ya no admite aportes; se deja como está.")


def sembrar(fabrica: sessionmaker[Session], ahora: datetime) -> bool:
    """Carga los datos de demo. Devuelve True si todo ya existía."""
    with fabrica() as sesion:
        existentes = _registrar(sesion, ahora)
        tokens = {
            n: sesiones.iniciar_sesion(sesion, n, CONTRASENA_DEMO, ahora).token
            for n in USUARIOS
        }
        for nombre, clave in CLAVES_CARGA.items():
            nucleo.cargar(sesion, tokens[nombre], clave, MONTO_CARGA, ahora)
        print("Cargas de $200.000 a ana, beto y carla listas.")

        cena, cena_existia = _bolsa(
            sesion,
            tokens["ana"],
            "cena",
            90_000,
            ["ana", "beto", "carla"],
            ahora + timedelta(days=7),
            True,
            ahora,
        )
        _aportar(sesion, tokens["beto"], "beto", CLAVE_APORTE_CENA, cena, "cena", ahora)

        vence, vence_existia = _bolsa(
            sesion,
            tokens["beto"],
            "vence_pronto",
            20_000,
            ["beto", "carla"],
            ahora + timedelta(minutes=3),
            False,  # al vencer devuelve todo: make vencer muestra la devolución
            ahora,
        )
        _aportar(
            sesion,
            tokens["carla"],
            "carla",
            CLAVE_APORTE_VENCE,
            vence,
            "vence_pronto",
            ahora,
        )
    return len(existentes) == len(USUARIOS) and cena_existia and vence_existia


def main(
    reloj: Callable[[], datetime] = _reloj,
    fabrica: sessionmaker[Session] | None = None,
) -> int:
    try:
        ahora = reloj()
        if fabrica is None:
            fabrica = crear_fabrica(obtener_motor())
        todo_existia = sembrar(fabrica, ahora)
    except Exception as error:  # noqa: BLE001 (solo el tipo: el texto puede traer secretos)
        print(f"ERROR ({type(error).__name__}): no se cargaron los datos de demo.")
        return 2
    if todo_existia:
        print("Los datos de demo ya existían; no se movió dinero nuevo.")
    else:
        print(
            "Datos de demo listos (contraseña de demo en el README). "
            "vence_pronto vence en 3 minutos: luego corre make vencer."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
