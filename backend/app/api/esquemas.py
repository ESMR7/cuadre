"""Modelos de entrada y salida (SPEC 5.2, 5.3, 9.1 y 9.3).

Entradas estrictas: el monto es un entero JSON (se rechazan 1000.0, "1000",
1e3 y true) y un campo desconocido es forma_invalida. Los límites del monto
los valida domain/ (monto_invalido, sobre_el_tope), no esta capa.
Todo patrón se valida contra el texto completo con re.fullmatch.
"""

import re
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, PlainSerializer, field_validator

_NOMBRE = re.compile(r"[a-z0-9_]{3,30}")
_CEDULA = re.compile(r"[0-9]{5,10}")
CONTRASENA_MIN_BYTES = 8
CONTRASENA_MAX_BYTES = 128


def _a_utc(valor: datetime) -> str:
    return valor.astimezone(UTC).isoformat().replace("+00:00", "Z")


FechaUTC = Annotated[datetime, PlainSerializer(_a_utc, return_type=str)]


class Entrada(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


def _validar_contrasena(valor: str) -> str:
    if not CONTRASENA_MIN_BYTES <= len(valor.encode("utf-8")) <= CONTRASENA_MAX_BYTES:
        raise ValueError("longitud fuera de rango")
    return valor


class Registro(Entrada):
    nombre_usuario: str
    cedula: str
    contrasena: str

    @field_validator("nombre_usuario")
    @classmethod
    def _nombre(cls, valor: str) -> str:
        valor = valor.lower()
        if _NOMBRE.fullmatch(valor) is None or valor == "sistema":
            raise ValueError("nombre de usuario inválido")
        return valor

    @field_validator("cedula")
    @classmethod
    def _cedula(cls, valor: str) -> str:
        if _CEDULA.fullmatch(valor) is None:
            raise ValueError("cédula inválida")
        return valor

    _contrasena = field_validator("contrasena")(_validar_contrasena)


class Login(Entrada):
    nombre_usuario: str
    contrasena: str

    @field_validator("nombre_usuario")
    @classmethod
    def _nombre(cls, valor: str) -> str:
        return valor.lower()

    _contrasena = field_validator("contrasena")(_validar_contrasena)


class Carga(Entrada):
    monto: int


class Transferencia(Entrada):
    destino: str
    monto: int

    @field_validator("destino")
    @classmethod
    def _destino(cls, valor: str) -> str:
        # Sin patrón: un destino que no es una cuenta personal da 404 en el servicio.
        return valor.lower()


class UsuarioSalida(BaseModel):
    nombre_usuario: str
    creado_en: FechaUTC


class SesionSalida(BaseModel):
    token: str
    expira_en: FechaUTC


class RenovacionSalida(BaseModel):
    expira_en: FechaUTC


class SaldoSalida(BaseModel):
    cuenta: str
    saldo: int


class EntradaHistorialSalida(BaseModel):
    tipo: str
    contrapartida: str
    monto: int
    creado_en: FechaUTC


class HistorialSalida(BaseModel):
    movimientos: list[EntradaHistorialSalida]
    desde: int
    cantidad: int


class TransaccionSalida(BaseModel):
    id: int
    tipo: str
    origen: str
    destino: str
    monto: int
    creado_en: FechaUTC


# --- Bolsas (SPEC 6.2 y 9.4) -------------------------------------------------

_NOMBRE_BOLSA = re.compile(r"[a-z0-9_]{1,40}")


class NuevaBolsa(Entrada):
    nombre: str
    total: int
    participantes: list[str]
    cuenta_objetivo: str
    fecha_limite: str
    transferir_al_vencer: bool

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor: str) -> str:
        valor = valor.lower()
        if _NOMBRE_BOLSA.fullmatch(valor) is None:
            raise ValueError("nombre de bolsa inválido")
        return valor

    @field_validator("participantes")
    @classmethod
    def _participantes(cls, valor: list[str]) -> list[str]:
        # Sin patrón: un nombre que no es una cuenta personal da 404 en el servicio.
        return [p.lower() for p in valor]

    @field_validator("cuenta_objetivo")
    @classmethod
    def _objetivo(cls, valor: str) -> str:
        return valor.lower()

    @field_validator("fecha_limite")
    @classmethod
    def _fecha(cls, valor: str) -> str:
        # Texto y no datetime: en modo estricto FastAPI rechaza el texto ISO, y
        # el modo laxo aceptaría enteros. Mensaje fijo: no repite lo recibido.
        try:
            fecha = datetime.fromisoformat(valor)
        except ValueError:
            raise ValueError("fecha inválida") from None
        if fecha.tzinfo is None:
            raise ValueError("fecha sin zona horaria")
        return valor

    def fecha_limite_utc(self) -> datetime:
        return datetime.fromisoformat(self.fecha_limite).astimezone(UTC)


class ConteoParticipantesSalida(BaseModel):
    total: int
    pendientes: int
    pagados: int
    por_confirmar: int
    retirados: int


class MiParticipacionSalida(BaseModel):
    parte: int
    estado: str


class BolsaSalida(BaseModel):
    id: UUID
    nombre: str
    creador: str
    cuenta_objetivo: str
    total: int
    fecha_limite: FechaUTC
    transferir_al_vencer: bool
    estado: str
    meta: int
    aportado: int
    transferido: int | None
    participantes: ConteoParticipantesSalida
    mi_participacion: MiParticipacionSalida


class ResumenBolsaSalida(BaseModel):
    id: UUID
    nombre: str
    estado: str
    fecha_limite: FechaUTC
    mi_parte: int
    mi_estado: str


class ListaBolsasSalida(BaseModel):
    bolsas: list[ResumenBolsaSalida]
    desde: int
    cantidad: int


class RetiroSalida(BaseModel):
    devolucion: TransaccionSalida | None


class ConfirmacionSalida(BaseModel):
    estado_bolsa: str
    mi_estado: str


class CancelacionSalida(BaseModel):
    estado_bolsa: str
