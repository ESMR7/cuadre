"""Hash canónico de una petición idempotente (SPEC 2.5).

La cuenta solicitante no entra en el hash: ya está en la llave
(cuenta_solicitante_id, clave).
"""

import hashlib
import json


def hash_peticion(
    operacion: str, ruta: dict[str, str], cuerpo: dict[str, object]
) -> str:
    """SHA-256 hex de {"operacion", "ruta", "cuerpo"} en JSON canónico.

    JSON con llaves ordenadas, sin espacios y sin escapar no ASCII.
    """
    canonico = json.dumps(
        {"operacion": operacion, "ruta": ruta, "cuerpo": cuerpo},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()
