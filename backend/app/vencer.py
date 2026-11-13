"""Comando del barrido: `python -m app.vencer` o `make vencer` (T14).

Recorte 3 (DECISIONS.md, 2026-11-13): "el barrido se ejecuta con un comando
(make vencer) y no con un hilo cada 60 segundos." "procesar_vencidas tiene las
mismas pruebas; solo cambia quién la dispara."

Sin lógica de negocio: lee el reloj una sola vez, arma la fábrica de sesiones
y llama a `procesar_vencidas`. Vive fuera de `services/` porque ese paquete no
lee el reloj (prueba de fronteras de capas).
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.orm import Session, sessionmaker

from app.db.sesion import crear_fabrica, obtener_motor
from app.services.barrido import procesar_vencidas

log = logging.getLogger("app.vencer")


def _reloj() -> datetime:
    return datetime.now(UTC)


def main(
    reloj: Callable[[], datetime] = _reloj,
    fabrica: sessionmaker[Session] | None = None,
) -> int:
    """0 si todas las bolsas se procesaron; 1 si alguna falló."""
    ahora = reloj()
    if fabrica is None:
        fabrica = crear_fabrica(obtener_motor())
    resumen = procesar_vencidas(fabrica, ahora)
    log.info(
        "Barrido en %s: %d procesadas, %d fallidas.",
        ahora.isoformat(),
        len(resumen.procesadas),
        len(resumen.fallidas),
    )
    return 1 if resumen.fallidas else 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
