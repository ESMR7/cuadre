"""Contraseñas con scrypt y tokens de sesión (SPEC 1.4). No toca la base.

Nada de este módulo escribe en logs ni incluye contraseñas, tokens o hashes
en excepciones.
"""

import base64
import binascii
import hashlib
import hmac
import secrets
from dataclasses import dataclass

from app.config import obtener_configuracion

ALGORITMO = "scrypt"
BYTES_SAL = 16
BYTES_HASH = 32
# Límites para un texto guardado: fuera de ellos se considera mal formado y
# no se calcula scrypt (evita que un valor absurdo agote la memoria o la CPU).
N_MAXIMO = 2**20
R_MAXIMO = 32
P_MAXIMO = 16
HOLGURA_MEMORIA = 1024 * 1024


@dataclass(frozen=True)
class ParametrosScrypt:
    n: int
    r: int
    p: int


def parametros_configurados() -> ParametrosScrypt:
    configuracion = obtener_configuracion()
    return ParametrosScrypt(
        n=configuracion.scrypt_n, r=configuracion.scrypt_r, p=configuracion.scrypt_p
    )


def memoria_maxima(parametros: ParametrosScrypt) -> int:
    """Memoria que necesita scrypt, 128*r*(n+p+2) bytes, más 1 MiB de holgura."""
    return 128 * parametros.r * (parametros.n + parametros.p + 2) + HOLGURA_MEMORIA


def _scrypt(contrasena: str, sal: bytes, parametros: ParametrosScrypt) -> bytes:
    return hashlib.scrypt(
        contrasena.encode("utf-8"),
        salt=sal,
        n=parametros.n,
        r=parametros.r,
        p=parametros.p,
        maxmem=memoria_maxima(parametros),
        dklen=BYTES_HASH,
    )


def hashear_contrasena(contrasena: str, parametros: ParametrosScrypt) -> str:
    """Devuelve `scrypt$n$r$p$<sal base64>$<hash base64>`."""
    sal = secrets.token_bytes(BYTES_SAL)
    digest = _scrypt(contrasena, sal, parametros)
    return "$".join(
        [
            ALGORITMO,
            str(parametros.n),
            str(parametros.r),
            str(parametros.p),
            base64.b64encode(sal).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        ]
    )


def _entero_positivo(texto: str) -> int | None:
    # isdecimal y ascii: rechaza "-1", "1.5", "+3" y dígitos no ASCII.
    if not (texto.isascii() and texto.isdecimal()):
        return None
    return int(texto)


def _decodificar(texto: str, largo: int) -> bytes | None:
    try:
        datos = base64.b64decode(texto, validate=True)
    except (binascii.Error, ValueError):
        return None
    return datos if len(datos) == largo else None


def _leer_guardado(guardado: str) -> tuple[ParametrosScrypt, bytes, bytes] | None:
    partes = guardado.split("$")
    if len(partes) != 6 or partes[0] != ALGORITMO:
        return None
    n, r, p = (_entero_positivo(parte) for parte in partes[1:4])
    if n is None or r is None or p is None:
        return None
    n_valido = 2 <= n <= N_MAXIMO and n & (n - 1) == 0
    if not (n_valido and 1 <= r <= R_MAXIMO and 1 <= p <= P_MAXIMO):
        return None
    sal = _decodificar(partes[4], BYTES_SAL)
    digest = _decodificar(partes[5], BYTES_HASH)
    if sal is None or digest is None:
        return None
    return ParametrosScrypt(n=n, r=r, p=p), sal, digest


def verificar_contrasena(contrasena: str, guardado: str) -> bool:
    """Recalcula scrypt con los parámetros y la sal guardados.

    Un texto guardado mal formado devuelve False, sin lanzar excepción.
    """
    leido = _leer_guardado(guardado)
    if leido is None:
        return False
    parametros, sal, digest = leido
    return hmac.compare_digest(_scrypt(contrasena, sal, parametros), digest)


def generar_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """SHA-256 en hexadecimal: lo único que se guarda del token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
