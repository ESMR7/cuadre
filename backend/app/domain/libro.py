"""Reglas puras del libro contable (SPEC 3.5, 3.8 y 3.9)."""

from typing import Final

# Tipo de transacción -> (tipo de cuenta origen, tipo de cuenta destino).
TIPOS_PERMITIDOS: Final[dict[str, tuple[str, str]]] = {
    "carga": ("sistema", "personal"),
    "transferencia": ("personal", "personal"),
    "aporte": ("personal", "bolsa"),
    "devolucion": ("bolsa", "personal"),
    "transferencia_final": ("bolsa", "personal"),
}


class LibroDescuadrado(Exception):
    """Una transacción no cumple la partida doble o la tabla 3.5.

    No es un ErrorDominio: indica un bug, no un error del usuario. Revierte
    la transacción y la API la deja salir como 500.
    """


def validar_tipos(tipo: str, tipo_origen: str, tipo_destino: str) -> None:
    if TIPOS_PERMITIDOS.get(tipo) != (tipo_origen, tipo_destino):
        raise LibroDescuadrado(
            f"Tipos de cuenta no permitidos para {tipo}: "
            f"{tipo_origen} -> {tipo_destino}."
        )


def verificar_patas(
    patas: dict[str, int], origen: str, destino: str, monto: int
) -> None:
    """Exige exactamente {origen: -monto, destino: +monto}."""
    if patas != {origen: -monto, destino: monto} or sum(patas.values()) != 0:
        raise LibroDescuadrado("Las patas de la transacción no cuadran.")
