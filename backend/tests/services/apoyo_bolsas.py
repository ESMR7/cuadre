"""Ayudas para las pruebas de bolsas (T10)."""

from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.services.bolsas import DetalleBolsa, crear_bolsa
from tests.services.apoyo_libro import AHORA

FECHA_LIMITE = AHORA + timedelta(days=1)
TRES = ("ana", "beto", "carla")


def crear(
    bd: sessionmaker[Session],
    token: str,
    nombre: str = "cena",
    total: int = 90_000,
    participantes: tuple[str, ...] = TRES,
    cuenta_objetivo: str = "olga",
    fecha_limite: datetime = FECHA_LIMITE,
    transferir_al_vencer: bool = True,
    ahora: datetime = AHORA,
) -> DetalleBolsa:
    with bd() as sesion:
        return crear_bolsa(
            sesion,
            token,
            nombre,
            total,
            list(participantes),
            cuenta_objetivo,
            fecha_limite,
            transferir_al_vencer,
            ahora,
        )


TABLAS = (
    "cuentas",
    "bolsas",
    "participantes",
    "transacciones",
    "movimientos",
    "claves_idempotencia",
)


def conteos(bd: sessionmaker[Session]) -> dict[str, int]:
    """Filas por tabla, para comprobar que algo no escribió nada."""
    with bd() as sesion:
        return {
            t: sesion.execute(text(f"SELECT count(*) FROM {t}")).scalar_one()
            for t in TABLAS
        }
