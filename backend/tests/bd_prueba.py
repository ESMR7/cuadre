"""Ciclo de vida de la base de pruebas (SPEC 10.2).

Toda función que crea, vacía o borra una base exige antes que su nombre
termine en `_test`. Ningún mensaje incluye la URL: solo el nombre de la base.
"""

import re
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import URL, Engine, create_engine, make_url, text
from sqlalchemy.pool import NullPool

RUTA_ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"

# SPEC 10.4: el pool de pruebas tiene al menos tantas conexiones como hilos.
POOL_PRUEBAS = 20
DESBORDE_PRUEBAS = 5

# El nombre completo, no solo el sufijo: así _nombre_citado nunca recibe
# comillas ni otros caracteres especiales.
PATRON_BASE_PRUEBA = re.compile(r"[a-z0-9_]+_test")


def exigir_base_de_prueba(url: str | URL) -> URL:
    url = make_url(url)
    nombre = url.database or ""
    if not PATRON_BASE_PRUEBA.fullmatch(nombre):
        raise RuntimeError(
            f"Base {nombre!r} rechazada: debe terminar en _test "
            "y usar solo a-z, 0-9 y _"
        )
    return url


def _ejecutar_en_mantenimiento(url: URL, sentencias: list[str]) -> None:
    """Ejecuta sentencias sobre la base `postgres` del mismo servidor."""
    motor = create_engine(
        url.set(database="postgres"), isolation_level="AUTOCOMMIT", poolclass=NullPool
    )
    try:
        with motor.connect() as conexion:
            for sentencia in sentencias:
                conexion.execute(text(sentencia))
    finally:
        motor.dispose()


def _nombre_citado(url: URL) -> str:
    """Nombre de la base entre comillas dobles; la guarda ya validó sus caracteres."""
    return '"' + url.database.replace('"', '""') + '"'


def recrear_base(url: str) -> None:
    url = exigir_base_de_prueba(url)
    nombre = _nombre_citado(url)
    _ejecutar_en_mantenimiento(
        url,
        [f"DROP DATABASE IF EXISTS {nombre} WITH (FORCE)", f"CREATE DATABASE {nombre}"],
    )


def migrar(url: str) -> None:
    url = exigir_base_de_prueba(url)
    configuracion = Config(str(RUTA_ALEMBIC_INI))
    # configparser interpreta '%': se escapa por si la contraseña lo tiene.
    url_texto = url.render_as_string(hide_password=False).replace("%", "%%")
    configuracion.set_main_option("sqlalchemy.url", url_texto)
    command.upgrade(configuracion, "head")


def vaciar_tablas(motor: Engine) -> None:
    """Vacía todas las tablas salvo alembic_version con un solo TRUNCATE."""
    exigir_base_de_prueba(motor.url)
    preparador = motor.dialect.identifier_preparer
    with motor.begin() as conexion:
        tablas = (
            conexion.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname = 'public' AND tablename <> 'alembic_version' "
                    "ORDER BY tablename"
                )
            )
            .scalars()
            .all()
        )
        if tablas:
            lista = ", ".join(preparador.quote_identifier(t) for t in tablas)
            conexion.execute(text(f"TRUNCATE {lista} RESTART IDENTITY CASCADE"))


def borrar_base(url: str) -> None:
    url = exigir_base_de_prueba(url)
    _ejecutar_en_mantenimiento(
        url, [f"DROP DATABASE IF EXISTS {_nombre_citado(url)} WITH (FORCE)"]
    )
