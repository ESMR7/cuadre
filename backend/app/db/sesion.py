"""Motor y fábrica de sesiones de SQLAlchemy."""

from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import exigir


def crear_motor(url: str, pool_size: int = 5, max_overflow: int = 10) -> Engine:
    return create_engine(
        url,
        isolation_level="READ COMMITTED",
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
    )


def crear_fabrica(motor: Engine) -> sessionmaker[Session]:
    # expire_on_commit=True (por defecto): tras un commit ningún objeto queda
    # con datos de la transacción anterior. El servicio arma su respuesta
    # antes del commit (H1).
    return sessionmaker(bind=motor)


@lru_cache
def obtener_motor() -> Engine:
    """Motor de la aplicación, creado al primer uso y no al importar."""
    return crear_motor(exigir("DATABASE_URL"))
