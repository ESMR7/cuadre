"""Contraseñas y tokens (SPEC 1.4). Sin base de datos."""

import ast
import base64
import hashlib
import inspect
import re

import pytest

from app.services import seguridad
from app.services.seguridad import (
    ParametrosScrypt,
    generar_token,
    hash_token,
    hashear_contrasena,
    parametros_configurados,
    verificar_contrasena,
)

RAPIDOS = ParametrosScrypt(n=2**14, r=8, p=1)
CONTRASENA = "clave-de-prueba-123"


def b64(datos: bytes) -> str:
    return base64.b64encode(datos).decode("ascii")


def test_parametros_configurados_usan_n_de_pruebas():
    assert parametros_configurados() == ParametrosScrypt(n=2**14, r=8, p=1)


def test_hash_tiene_formato_scrypt_con_parametros_y_sal_de_16_bytes():
    guardado = hashear_contrasena(CONTRASENA, RAPIDOS)
    partes = guardado.split("$")
    assert partes[:4] == ["scrypt", "16384", "8", "1"]
    assert len(partes) == 6
    assert len(base64.b64decode(partes[4], validate=True)) == 16
    assert len(base64.b64decode(partes[5], validate=True)) == 32


def test_hash_coincide_con_hashlib_scrypt():
    guardado = hashear_contrasena(CONTRASENA, RAPIDOS)
    _, n, r, p, sal, digest = guardado.split("$")
    esperado = hashlib.scrypt(
        CONTRASENA.encode(),
        salt=base64.b64decode(sal),
        n=int(n),
        r=int(r),
        p=int(p),
        maxmem=64 * 1024 * 1024,
        dklen=32,
    )
    assert base64.b64decode(digest) == esperado


def test_hash_guardado_no_contiene_la_contrasena():
    guardado = hashear_contrasena(CONTRASENA, RAPIDOS)
    assert CONTRASENA not in guardado
    assert b64(CONTRASENA.encode()) not in guardado


def test_verificar_acepta_la_correcta_y_rechaza_otra():
    guardado = hashear_contrasena(CONTRASENA, RAPIDOS)
    assert verificar_contrasena(CONTRASENA, guardado) is True
    assert verificar_contrasena(CONTRASENA + "x", guardado) is False


def test_dos_hashes_de_la_misma_contrasena_difieren():
    assert hashear_contrasena(CONTRASENA, RAPIDOS) != hashear_contrasena(
        CONTRASENA, RAPIDOS
    )


def test_verificar_usa_los_parametros_guardados():
    otros = ParametrosScrypt(n=2**12, r=4, p=2)
    guardado = hashear_contrasena(CONTRASENA, otros)
    assert guardado.startswith("scrypt$4096$4$2$")
    assert verificar_contrasena(CONTRASENA, guardado) is True


def test_hash_con_parametros_owasp_funciona():
    # maxmem debe cubrir 128*r*(n+p+2); con N=2^17 y r=8 pasa de 128 MiB.
    owasp = ParametrosScrypt(n=2**17, r=8, p=1)
    guardado = hashear_contrasena(CONTRASENA, owasp)
    assert verificar_contrasena(CONTRASENA, guardado) is True


def test_verificar_usa_compare_digest_y_no_igualdad():
    arbol = ast.parse(inspect.getsource(seguridad.verificar_contrasena))
    llamadas = [
        n.func.attr
        for n in ast.walk(arbol)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
    ]
    assert "compare_digest" in llamadas
    comparaciones = [n for n in ast.walk(arbol) if isinstance(n, ast.Compare)]
    assert not any(
        isinstance(op, ast.Eq | ast.NotEq) for c in comparaciones for op in c.ops
    )


SAL = b64(b"s" * 16)
DIGEST = b64(b"h" * 32)


@pytest.mark.parametrize(
    "guardado",
    [
        "",
        "scrypt",
        f"scrypt$16384$8$1${SAL}",
        f"scrypt$16384$8$1${SAL}${DIGEST}$extra",
        f"bcrypt$16384$8$1${SAL}${DIGEST}",
        f"scrypt$abc$8$1${SAL}${DIGEST}",
        f"scrypt$16384$x$1${SAL}${DIGEST}",
        f"scrypt$16384$8$1.5${SAL}${DIGEST}",
        f"scrypt$16384$8$1$no-es-base64!${DIGEST}",
        f"scrypt$16384$8$1${SAL}$###",
        f"scrypt$16384$8$1${b64(b'corta')}${DIGEST}",
        f"scrypt$16384$8$1${SAL}${b64(b'corto')}",
        f"scrypt$0$8$1${SAL}${DIGEST}",
        f"scrypt$1$8$1${SAL}${DIGEST}",
        f"scrypt$1000$8$1${SAL}${DIGEST}",
        f"scrypt${2**40}$8$1${SAL}${DIGEST}",
        f"scrypt$16384$0$1${SAL}${DIGEST}",
        f"scrypt$16384$999999$1${SAL}${DIGEST}",
        f"scrypt$16384$8$0${SAL}${DIGEST}",
        f"scrypt$16384$8$999999${SAL}${DIGEST}",
        f"scrypt$-16384$8$1${SAL}${DIGEST}",
    ],
)
def test_verificar_guardado_mal_formado_devuelve_false(guardado: str):
    assert verificar_contrasena(CONTRASENA, guardado) is False


def test_hash_token_es_sha256_hex_de_64():
    token = "token-de-prueba"
    resultado = hash_token(token)
    assert re.fullmatch(r"[0-9a-f]{64}", resultado)
    assert resultado == hashlib.sha256(token.encode()).hexdigest()


def test_tokens_generados_son_distintos_y_largos():
    tokens = {generar_token() for _ in range(50)}
    assert len(tokens) == 50
    assert all(len(t) >= 43 for t in tokens)
    assert all(re.fullmatch(r"[A-Za-z0-9_-]+", t) for t in tokens)
