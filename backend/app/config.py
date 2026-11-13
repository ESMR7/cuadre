"""Configuración leída del entorno, con el .env de la raíz como respaldo.

Nunca se imprime ni se escribe en logs: contiene credenciales.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

RUTA_ENV = Path(__file__).resolve().parents[2] / ".env"


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(env_file=RUTA_ENV, extra="ignore")

    database_url: str | None = None
    test_database_url: str | None = None

    def __repr__(self) -> str:
        return "Configuracion(<oculta>)"

    __str__ = __repr__


@lru_cache
def obtener_configuracion() -> Configuracion:
    return Configuracion()


def exigir(nombre: str, configuracion: Configuracion | None = None) -> str:
    """Devuelve el valor de la variable o lanza un error que solo la nombra.

    `configuracion` existe solo para las pruebas; la aplicación no lo pasa.
    """
    if configuracion is None:
        configuracion = obtener_configuracion()
    valor = getattr(configuracion, nombre.lower(), None)
    if not valor:
        raise RuntimeError(f"Falta la variable de entorno {nombre}")
    return valor
