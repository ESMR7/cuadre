"""Límites del negocio en un solo lugar (SPEC 1.5)."""

from typing import Final

# Tope por carga, transferencia o aporte: operaciones que inicia un usuario.
# Las devoluciones y la transferencia final no tienen tope.
TOPE_OPERACION: Final[int] = 50_000_000
