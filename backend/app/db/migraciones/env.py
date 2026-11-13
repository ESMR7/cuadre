"""Entorno de Alembic. Solo modo online."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.config import exigir
from app.db.modelos import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def obtener_url() -> str:
    """La URL del fixture de pruebas si viene; si no, DATABASE_URL."""
    return config.get_main_option("sqlalchemy.url") or exigir("DATABASE_URL")


def ejecutar_migraciones() -> None:
    motor = create_engine(obtener_url(), poolclass=pool.NullPool)
    try:
        with motor.connect() as conexion:
            context.configure(connection=conexion, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        motor.dispose()


if context.is_offline_mode():
    raise RuntimeError("Cuadre solo migra en modo online")

ejecutar_migraciones()
