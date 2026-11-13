"""Límites del negocio en un solo lugar (SPEC 1.5)."""

from datetime import timedelta
from typing import Final

# Tope por carga, transferencia o aporte: operaciones que inicia un usuario.
# Las devoluciones y la transferencia final no tienen tope.
TOPE_OPERACION: Final[int] = 50_000_000

# Vigencia de un token desde el login o la última renovación (SPEC 1.4).
DURACION_SESION: Final[timedelta] = timedelta(minutes=20)
