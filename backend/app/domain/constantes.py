"""Límites del negocio en un solo lugar (SPEC 1.5)."""

from datetime import timedelta
from typing import Final

# Tope por carga, transferencia o aporte: operaciones que inicia un usuario.
# Las devoluciones y la transferencia final no tienen tope.
TOPE_OPERACION: Final[int] = 50_000_000

# Vigencia de un token desde el login o la última renovación (SPEC 1.4).
DURACION_SESION: Final[timedelta] = timedelta(minutes=20)

# Bolsas (SPEC 1.5 y 6.2). Todos son constantes configurables.
MIN_PARTICIPANTES: Final[int] = 2
MAX_PARTICIPANTES: Final[int] = 50
TOTAL_MINIMO: Final[int] = 10_000
# Total máximo de una bolsa: N × (TOPE_OPERACION − MARGEN_TOTAL). El margen
# deja espacio al sobrante del creador (como máximo N − 1 ≤ 49).
MARGEN_TOTAL: Final[int] = 10_000
ANTICIPACION_MINIMA: Final[timedelta] = timedelta(minutes=2)
ANTICIPACION_MAXIMA: Final[timedelta] = timedelta(days=30)
