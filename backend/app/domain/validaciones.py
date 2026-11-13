"""Validaciones puras de negocio (SPEC 2.1 y 5.6)."""

from app.domain.constantes import TOPE_OPERACION
from app.domain.errores import MontoInvalido, SobreElTope, TransferenciaASiMismo


def validar_monto(monto: object) -> int:
    """Valida un monto de una operación de usuario y lo devuelve sin cambios.

    Debe ser un `int` exacto, mayor que cero y no mayor que `TOPE_OPERACION`.
    Rechaza `bool` (en Python `True` es un `int`), `float` (aunque sea `1000.0`),
    `Decimal`, texto y subclases de `int`. Nunca convierte ni redondea.

    En el flujo normal un decimal llega a la API como `forma_invalida`
    (SPEC 2.6) y nunca llega aquí; el rechazo de tipos no enteros es defensa extra.
    """
    if type(monto) is not int:
        raise MontoInvalido("El monto debe ser un entero.")
    if monto <= 0:
        raise MontoInvalido("El monto debe ser mayor que cero.")
    if monto > TOPE_OPERACION:
        raise SobreElTope("El monto supera el tope por operación.")
    return monto


def validar_destino_distinto(origen_id: str, destino_id: str) -> None:
    """Rechaza una transferencia de una cuenta a sí misma.

    Los ids llegan ya normalizados (la API convierte a minúsculas, SPEC 3.3),
    así que la comparación es exacta.
    """
    if origen_id == destino_id:
        raise TransferenciaASiMismo("No se puede transferir a la propia cuenta.")
