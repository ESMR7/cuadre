"""Hash canónico de la petición (SPEC 2.5)."""

import hashlib
import json

from app.domain.idempotencia import hash_peticion


def test_hash_es_sha256_hex_de_json_canonico():
    esperado = hashlib.sha256(
        json.dumps(
            {
                "cuerpo": {"destino": "beto", "monto": 100},
                "operacion": "transferir",
                "ruta": {},
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    assert (
        hash_peticion("transferir", {}, {"destino": "beto", "monto": 100}) == esperado
    )


def test_hash_igual_con_llaves_en_otro_orden():
    a = hash_peticion("transferir", {}, {"destino": "beto", "monto": 100})
    b = hash_peticion("transferir", {}, {"monto": 100, "destino": "beto"})
    assert a == b


def test_hash_cambia_con_operacion_ruta_o_cuerpo():
    base = hash_peticion("cargar", {}, {"monto": 100})
    assert hash_peticion("transferir", {}, {"monto": 100}) != base
    assert hash_peticion("cargar", {"bolsa_id": "x"}, {"monto": 100}) != base
    assert hash_peticion("cargar", {}, {"monto": 101}) != base
