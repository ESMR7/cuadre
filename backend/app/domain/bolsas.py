"""Reglas puras de las bolsas: división, creación, meta y transiciones.

SPEC 3.7, 6.1 a 6.4, 7.1 a 7.4 y 8.2. Sin base de datos, sin FastAPI y sin
leer el reloj: toda función que depende de la hora recibe `ahora`. Ninguna
función muta los participantes que recibe: devuelve un diccionario nuevo.
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from app.domain.constantes import (
    ANTICIPACION_MAXIMA,
    ANTICIPACION_MINIMA,
    MARGEN_TOTAL,
    MAX_PARTICIPANTES,
    MIN_PARTICIPANTES,
    TOPE_OPERACION,
    TOTAL_MINIMO,
)
from app.domain.errores import (
    EstadoInvalido,
    FechaLimiteInvalida,
    FueraDePlazo,
    ParticipantesInvalidos,
    SinPermiso,
    TotalInvalido,
)


class EstadoBolsa(StrEnum):
    ABIERTA = "abierta"
    CANCELADA = "cancelada"
    LIQUIDANDO = "liquidando"
    CERRADA = "cerrada"


class EstadoParticipante(StrEnum):
    PENDIENTE = "pendiente"
    PAGADO = "pagado"
    POR_CONFIRMAR = "por_confirmar"
    RETIRADO = "retirado"


Participantes = Mapping[str, EstadoParticipante]

_PAGARON = {EstadoParticipante.PAGADO, EstadoParticipante.POR_CONFIRMAR}


@dataclass(frozen=True)
class ResultadoTransicion:
    """Estados nuevos tras un evento.

    - `completa`: todos los activos quedaron en `pagado` (o, al cerrar la
      liquidación con `transferir`, quedan pagados); el servicio debe hacer la
      transferencia final por el saldo en la misma transacción.
    - `cierra`: la bolsa pasa a `cerrada`. **No implica saldo cero**: puede
      quedar dinero (por ejemplo, el último activo se retira habiendo pagado).
      Con `cierra=True` el servicio debe hacer antes la devolución o la
      transferencia final que corresponda y comprobar que el saldo de la
      cuenta de la bolsa es 0 antes de cerrar (SPEC 6.1 y 7.4).
    - `habia_pagado`: solo en `retirarse`; si es verdadero, el servicio
      devuelve la deuda recalculada desde el libro (SPEC 3.6).
    """

    estado_bolsa: EstadoBolsa
    participantes: dict[str, EstadoParticipante]
    completa: bool = False
    cierra: bool = False
    habia_pagado: bool = False


# --- División y creación -----------------------------------------------------


def dividir(total: int, participantes: Sequence[str], creador: str) -> dict[str, int]:
    """Divide `total` en partes exactas (SPEC 3.7).

    Base = total // N y resto = total % N. Cada participante paga la base y
    el creador, la base más el resto. La suma de las partes es el total.
    """
    base, resto = divmod(total, len(participantes))
    partes = {usuario: base for usuario in participantes}
    partes[creador] = base + resto
    return partes


def validar_creacion(
    creador: str,
    participantes: Sequence[str],
    total: int,
    fecha_limite: datetime,
    ahora: datetime,
    *,
    anticipacion_minima: timedelta = ANTICIPACION_MINIMA,
    anticipacion_maxima: timedelta = ANTICIPACION_MAXIMA,
) -> None:
    """Valida participantes, total y fecha límite al crear (SPEC 6.2).

    Orden: participantes, total y fecha. El total máximo depende de N, así
    que solo se revisa con una lista válida. Las fechas se comparan como
    instantes, así que la zona horaria de entrada no cambia el resultado.
    """
    n = len(participantes)
    if (
        creador not in participantes
        or len(set(participantes)) != n
        or not MIN_PARTICIPANTES <= n <= MAX_PARTICIPANTES
    ):
        raise ParticipantesInvalidos(
            "La lista debe incluir al creador, sin repetidos, "
            f"con entre {MIN_PARTICIPANTES} y {MAX_PARTICIPANTES} participantes."
        )
    if not TOTAL_MINIMO <= total <= n * (TOPE_OPERACION - MARGEN_TOTAL):
        raise TotalInvalido("El total de la bolsa está fuera de los límites.")
    if fecha_limite.utcoffset() is None:
        # Defensa extra: la API ya rechaza fechas sin zona (forma_invalida).
        raise FechaLimiteInvalida("La fecha límite debe tener zona horaria.")
    if not ahora + anticipacion_minima <= fecha_limite <= ahora + anticipacion_maxima:
        raise FechaLimiteInvalida("La fecha límite está fuera de la ventana permitida.")


def calcular_meta(partes: Mapping[str, int], participantes: Participantes) -> int:
    """Meta = suma de las partes de los activos (SPEC 6.1). Nunca se guarda."""
    return sum(
        partes[usuario]
        for usuario, estado in participantes.items()
        if estado != EstadoParticipante.RETIRADO
    )


# --- Revisiones comunes ------------------------------------------------------


def verificar_operable(
    estado_bolsa: EstadoBolsa,
    permitidos: Collection[EstadoBolsa],
    fecha_limite: datetime,
    ahora: datetime,
) -> None:
    """Primero el estado y después el plazo (SPEC 8.2).

    La bolsa está vigente solo si `ahora < fecha_limite`.
    """
    if estado_bolsa not in permitidos:
        raise EstadoInvalido(f"La bolsa está {estado_bolsa}.")
    if ahora >= fecha_limite:
        raise FueraDePlazo("La fecha límite ya pasó.")


def _estado_de(participantes: Participantes, usuario: str) -> EstadoParticipante:
    """Defensa extra: el servicio ya verificó que el usuario figura (403)."""
    if usuario not in participantes:
        raise SinPermiso("No figura en la bolsa.")
    return participantes[usuario]


def _todos_activos_pagados(participantes: Participantes) -> bool:
    """La bolsa se completa si hay activos y todos están en `pagado` (6.4)."""
    activos = [e for e in participantes.values() if e != EstadoParticipante.RETIRADO]
    return bool(activos) and all(e == EstadoParticipante.PAGADO for e in activos)


def _hay_activos(participantes: Participantes) -> bool:
    return any(e != EstadoParticipante.RETIRADO for e in participantes.values())


def _tras_pago(
    estado_bolsa: EstadoBolsa, nuevos: dict[str, EstadoParticipante]
) -> ResultadoTransicion:
    """Resultado de aportar o confirmar: completa si todos los activos pagaron."""
    if _todos_activos_pagados(nuevos):
        return ResultadoTransicion(
            EstadoBolsa.CERRADA, nuevos, completa=True, cierra=True
        )
    return ResultadoTransicion(estado_bolsa, nuevos)


# --- Eventos de usuario ------------------------------------------------------


def aportar(
    estado_bolsa: EstadoBolsa,
    participantes: Participantes,
    usuario: str,
    fecha_limite: datetime,
    ahora: datetime,
) -> ResultadoTransicion:
    """`pendiente` → `pagado` en una bolsa `abierta` (SPEC 6.5)."""
    verificar_operable(estado_bolsa, {EstadoBolsa.ABIERTA}, fecha_limite, ahora)
    if _estado_de(participantes, usuario) != EstadoParticipante.PENDIENTE:
        raise EstadoInvalido("Solo un participante pendiente puede aportar.")
    nuevos = dict(participantes)
    nuevos[usuario] = EstadoParticipante.PAGADO
    return _tras_pago(estado_bolsa, nuevos)


def retirarse(
    estado_bolsa: EstadoBolsa,
    participantes: Participantes,
    usuario: str,
    fecha_limite: datetime,
    ahora: datetime,
) -> ResultadoTransicion:
    """Retiro en una bolsa `abierta` o `cancelada` (SPEC 6.6).

    Quien se retira pasa a `retirado` y todos los demás en `pagado` pasan a
    `por_confirmar`, porque la meta baja aunque no hubiera pagado. Un retiro
    nunca completa la bolsa. Si no quedan activos, la bolsa se cierra.
    """
    verificar_operable(
        estado_bolsa, {EstadoBolsa.ABIERTA, EstadoBolsa.CANCELADA}, fecha_limite, ahora
    )
    actual = _estado_de(participantes, usuario)
    if actual == EstadoParticipante.RETIRADO:
        raise EstadoInvalido("El participante ya se retiró.")
    nuevos = {
        u: EstadoParticipante.POR_CONFIRMAR if e == EstadoParticipante.PAGADO else e
        for u, e in participantes.items()
    }
    nuevos[usuario] = EstadoParticipante.RETIRADO
    habia_pagado = actual in _PAGARON
    if not _hay_activos(nuevos):
        return ResultadoTransicion(
            EstadoBolsa.CERRADA, nuevos, cierra=True, habia_pagado=habia_pagado
        )
    return ResultadoTransicion(estado_bolsa, nuevos, habia_pagado=habia_pagado)


def confirmar(
    estado_bolsa: EstadoBolsa,
    participantes: Participantes,
    usuario: str,
    fecha_limite: datetime,
    ahora: datetime,
) -> ResultadoTransicion:
    """`por_confirmar` → `pagado` en una bolsa `abierta` o `cancelada` (6.7)."""
    verificar_operable(
        estado_bolsa, {EstadoBolsa.ABIERTA, EstadoBolsa.CANCELADA}, fecha_limite, ahora
    )
    if _estado_de(participantes, usuario) != EstadoParticipante.POR_CONFIRMAR:
        raise EstadoInvalido("Solo un participante por confirmar puede confirmar.")
    nuevos = dict(participantes)
    nuevos[usuario] = EstadoParticipante.PAGADO
    return _tras_pago(estado_bolsa, nuevos)


def cancelar(
    estado_bolsa: EstadoBolsa,
    participantes: Participantes,
    transferir_al_vencer: bool,
    saldo_bolsa: int,
    fecha_limite: datetime,
    ahora: datetime,
) -> ResultadoTransicion:
    """Cancelación de una bolsa `abierta` (SPEC 7.1). No mueve dinero.

    Que quien cancela sea el creador (403) lo verifica el servicio.

    `saldo_bolsa` es el saldo de la cuenta de la bolsa, que el servicio debe
    leer con la fila de la bolsa ya bloqueada (`SELECT ... FOR UPDATE`) y con
    `populate_existing`, para que no cambie entre la lectura y la escritura.

    - Devolver: todos pasan a `retirado`; `cerrada` si el saldo es 0 y
      `liquidando` si no (el barrido devuelve).
    - Transferir: `pendiente` → `retirado` y `pagado` → `por_confirmar`;
      `cancelada` si queda algún activo y `cerrada` si no.
    """
    verificar_operable(estado_bolsa, {EstadoBolsa.ABIERTA}, fecha_limite, ahora)
    if not transferir_al_vencer:
        nuevos = {u: EstadoParticipante.RETIRADO for u in participantes}
        if saldo_bolsa == 0:
            return ResultadoTransicion(EstadoBolsa.CERRADA, nuevos, cierra=True)
        return ResultadoTransicion(EstadoBolsa.LIQUIDANDO, nuevos)
    cambio = {
        EstadoParticipante.PENDIENTE: EstadoParticipante.RETIRADO,
        EstadoParticipante.PAGADO: EstadoParticipante.POR_CONFIRMAR,
    }
    nuevos = {u: cambio.get(e, e) for u, e in participantes.items()}
    if not _hay_activos(nuevos):
        return ResultadoTransicion(EstadoBolsa.CERRADA, nuevos, cierra=True)
    return ResultadoTransicion(EstadoBolsa.CANCELADA, nuevos)


# --- Eventos del barrido -----------------------------------------------------


def preparar_liquidacion(
    estado_bolsa: EstadoBolsa,
    participantes: Participantes,
    transferir_al_vencer: bool,
    fecha_limite: datetime,
    ahora: datetime,
) -> ResultadoTransicion:
    """Paso 1 del barrido: una bolsa vencida pasa a `liquidando` (SPEC 7.2).

    Quien no está en `pagado` pasa a `retirado`; con la política de devolver,
    también los `pagado`. No mueve dinero.
    """
    if estado_bolsa not in {EstadoBolsa.ABIERTA, EstadoBolsa.CANCELADA}:
        raise EstadoInvalido(f"La bolsa está {estado_bolsa}.")
    if ahora < fecha_limite:
        raise EstadoInvalido("La bolsa todavía no vence.")
    nuevos = {
        u: e
        if transferir_al_vencer and e == EstadoParticipante.PAGADO
        else EstadoParticipante.RETIRADO
        for u, e in participantes.items()
    }
    return ResultadoTransicion(EstadoBolsa.LIQUIDANDO, nuevos)


def cerrar_liquidacion(
    estado_bolsa: EstadoBolsa,
    participantes: Participantes,
    transferir_al_vencer: bool,
    hay_deudas_pendientes: bool,
) -> ResultadoTransicion:
    """Paso 3 del barrido: decide si una bolsa `liquidando` se cierra (7.4).

    Si queda un `retirado` con deuda, no cierra y el siguiente ciclo retoma.
    Si no, cierra; `completa` indica que corresponde la transferencia final
    (política de transferir y participantes en `pagado`). El servicio aún
    debe comprobar que el saldo es exactamente la suma de sus partes, o 0 si
    no hay transferencia, antes de cerrar.
    """
    if estado_bolsa != EstadoBolsa.LIQUIDANDO:
        raise EstadoInvalido(f"La bolsa está {estado_bolsa}.")
    nuevos = dict(participantes)
    if hay_deudas_pendientes:
        return ResultadoTransicion(EstadoBolsa.LIQUIDANDO, nuevos)
    completa = transferir_al_vencer and any(
        e == EstadoParticipante.PAGADO for e in nuevos.values()
    )
    return ResultadoTransicion(
        EstadoBolsa.CERRADA, nuevos, completa=completa, cierra=True
    )
