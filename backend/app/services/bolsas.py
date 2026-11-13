"""Crear y consultar bolsas (SPEC 6.1, 6.2 y 9.4).

Crear no mueve dinero, no lleva clave y no toma bloqueos explícitos: las
llaves foráneas toman `FOR KEY SHARE`, que no choca con `FOR NO KEY UPDATE`
(SPEC 8.1). Las consultas no bloquean filas ni usan reintentos.
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.modelos import Bolsa, Cuenta, Participante
from app.domain.bolsas import (
    EstadoBolsa,
    EstadoParticipante,
    calcular_meta,
    dividir,
    validar_creacion,
)
from app.domain.errores import NoEncontrado, NombreEnUso, SinPermiso
from app.domain.validaciones import validar_paginacion
from app.services.consultas import EntradaHistorial
from app.services.errores_bd import nombre_restriccion
from app.services.sesiones import autenticar


@dataclass(frozen=True)
class ConteoParticipantes:
    total: int
    pendientes: int
    pagados: int
    por_confirmar: int
    retirados: int


@dataclass(frozen=True)
class MiParticipacion:
    parte: int
    estado: str


@dataclass(frozen=True)
class DetalleBolsa:
    """Lo que ve un participante: términos, totales y solo lo propio (9.4)."""

    id: UUID
    nombre: str
    creador: str
    cuenta_objetivo: str
    total: int
    fecha_limite: datetime
    transferir_al_vencer: bool
    estado: str
    meta: int
    aportado: int
    transferido: int | None
    participantes: ConteoParticipantes
    mi_participacion: MiParticipacion


@dataclass(frozen=True)
class ResumenBolsa:
    id: UUID
    nombre: str
    estado: str
    fecha_limite: datetime
    mi_parte: int
    mi_estado: str


_CUENTAS_PERSONALES = text(
    "SELECT id FROM cuentas WHERE id = ANY(:ids) AND tipo = 'personal'"
)
_SALDO = text("SELECT saldo FROM cuentas WHERE id = :cuenta")
_TRANSFERIDO = text(
    "SELECT monto FROM transacciones "
    "WHERE tipo = 'transferencia_final' AND cuenta_origen_id = :cuenta"
)
_PARTICIPANTES = text(
    "SELECT cuenta_id, parte, estado FROM participantes WHERE bolsa_id = :bolsa"
)
_MIS_BOLSAS = text(
    """
    SELECT b.id, b.nombre, b.estado, b.fecha_limite, p.parte, p.estado AS mi_estado
    FROM participantes p
    JOIN bolsas b ON b.id = p.bolsa_id
    WHERE p.cuenta_id = :cuenta
    ORDER BY b.creada_en DESC, b.id DESC
    LIMIT :cantidad OFFSET :desde
    """
)
# Solo aportes y devoluciones entre quien pide y la bolsa (SPEC 9.4).
_MIS_MOVIMIENTOS = text(
    """
    SELECT t.tipo,
           CASE WHEN t.cuenta_origen_id = :cuenta THEN t.cuenta_destino_id
                ELSE t.cuenta_origen_id END AS contrapartida,
           m.monto,
           t.creado_en
    FROM movimientos m
    JOIN transacciones t ON t.id = m.transaccion_id
    WHERE m.cuenta_id = :cuenta
      AND t.tipo IN ('aporte', 'devolucion')
      AND (t.cuenta_origen_id = :bolsa OR t.cuenta_destino_id = :bolsa)
    ORDER BY t.creado_en DESC, t.id DESC
    LIMIT :cantidad OFFSET :desde
    """
)


# --- Crear -------------------------------------------------------------------


def crear_bolsa(
    sesion: Session,
    token: str,
    nombre: str,
    total: int,
    participantes: Sequence[str],
    cuenta_objetivo: str,
    fecha_limite: datetime,
    transferir_al_vencer: bool,
    ahora: datetime,
) -> DetalleBolsa:
    """Crea la cuenta de la bolsa, la bolsa y sus participantes (SPEC 6.2).

    Recibe nombres ya normalizados por la API. Orden: sesión (401), dominio
    (422), cuentas personales (404) y nombre único (409). Todo en una sola
    transacción; la respuesta se arma antes del commit.
    """
    with sesion.begin():
        creador = autenticar(sesion, token, ahora).cuenta_id
        validar_creacion(creador, participantes, total, fecha_limite, ahora)
        _verificar_cuentas_personales(sesion, {*participantes, cuenta_objetivo})
        partes = dividir(total, participantes, creador)

        cuenta_bolsa = f"bolsa-{creador}-{nombre}"
        try:
            sesion.add(Cuenta(id=cuenta_bolsa, tipo="bolsa", saldo=0, creada_en=ahora))
            sesion.flush()
        except IntegrityError as error:
            if nombre_restriccion(error) == "pk_cuentas":
                raise NombreEnUso() from None
            raise

        bolsa = Bolsa(
            nombre=nombre,
            total=total,
            cuenta_id=cuenta_bolsa,
            creador_cuenta_id=creador,
            cuenta_objetivo_id=cuenta_objetivo,
            transferir_al_vencer=transferir_al_vencer,
            fecha_limite=fecha_limite,
            estado=EstadoBolsa.ABIERTA.value,
            creada_en=ahora,
        )
        sesion.add(bolsa)
        sesion.flush()
        sesion.add_all(
            Participante(
                bolsa_id=bolsa.id,
                cuenta_id=usuario,
                parte=parte,
                estado=EstadoParticipante.PENDIENTE.value,
            )
            for usuario, parte in partes.items()
        )
        sesion.flush()
        return _armar_detalle(sesion, bolsa, creador)


def _verificar_cuentas_personales(sesion: Session, ids: set[str]) -> None:
    """Toda cuenta debe existir y ser personal; si no, no_encontrado.

    Así `sistema` y las cuentas `bolsa-...` se rechazan igual que una
    inexistente.
    """
    encontradas = set(sesion.execute(_CUENTAS_PERSONALES, {"ids": list(ids)}).scalars())
    if encontradas != ids:
        raise NoEncontrado("Algún participante o la cuenta objetivo no existe.")


# --- Consultas ---------------------------------------------------------------


def _lectura_consistente(sesion: Session) -> None:
    """Una sola foto de la base para varias lecturas (como make check).

    En READ COMMITTED un aporte confirmado entre dos lecturas daría un
    detalle incoherente: un participante en `pagado` sin su parte en
    `aportado`. Debe ser la primera sentencia de la transacción.
    """
    sesion.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))


def _bolsa_visible(sesion: Session, bolsa_id: UUID, mi_cuenta: str) -> Bolsa:
    """La bolsa si existe (404) y quien pide figura en ella (403).

    Los retirados siguen figurando, así que la ven.
    """
    bolsa = sesion.get(Bolsa, bolsa_id)
    if bolsa is None:
        raise NoEncontrado("La bolsa no existe.")
    if sesion.get(Participante, (bolsa_id, mi_cuenta)) is None:
        raise SinPermiso("No figura en la bolsa.")
    return bolsa


def _armar_detalle(sesion: Session, bolsa: Bolsa, mi_cuenta: str) -> DetalleBolsa:
    filas = sesion.execute(_PARTICIPANTES, {"bolsa": bolsa.id}).all()
    partes = {f.cuenta_id: f.parte for f in filas}
    estados = {f.cuenta_id: EstadoParticipante(f.estado) for f in filas}
    por_estado = Counter(estados.values())
    aportado = sesion.execute(_SALDO, {"cuenta": bolsa.cuenta_id}).scalar_one()
    transferido = sesion.execute(
        _TRANSFERIDO, {"cuenta": bolsa.cuenta_id}
    ).scalar_one_or_none()
    return DetalleBolsa(
        id=bolsa.id,
        nombre=bolsa.nombre,
        creador=bolsa.creador_cuenta_id,
        cuenta_objetivo=bolsa.cuenta_objetivo_id,
        total=bolsa.total,
        fecha_limite=bolsa.fecha_limite,
        transferir_al_vencer=bolsa.transferir_al_vencer,
        estado=bolsa.estado,
        meta=calcular_meta(partes, estados),
        aportado=aportado,
        transferido=transferido,
        participantes=ConteoParticipantes(
            total=len(filas),
            pendientes=por_estado[EstadoParticipante.PENDIENTE],
            pagados=por_estado[EstadoParticipante.PAGADO],
            por_confirmar=por_estado[EstadoParticipante.POR_CONFIRMAR],
            retirados=por_estado[EstadoParticipante.RETIRADO],
        ),
        mi_participacion=MiParticipacion(
            parte=partes[mi_cuenta], estado=estados[mi_cuenta].value
        ),
    )


def consultar_bolsa(
    sesion: Session, token: str, bolsa_id: UUID, ahora: datetime
) -> DetalleBolsa:
    with sesion.begin():
        _lectura_consistente(sesion)
        mi_cuenta = autenticar(sesion, token, ahora).cuenta_id
        bolsa = _bolsa_visible(sesion, bolsa_id, mi_cuenta)
        return _armar_detalle(sesion, bolsa, mi_cuenta)


def listar_bolsas(
    sesion: Session, token: str, desde: int, cantidad: int, ahora: datetime
) -> list[ResumenBolsa]:
    """Mis bolsas, de la más reciente a la más antigua (SPEC 9.2).

    Una sola consulta: basta READ ONLY en READ COMMITTED.
    """
    with sesion.begin():
        sesion.execute(text("SET TRANSACTION READ ONLY"))
        mi_cuenta = autenticar(sesion, token, ahora).cuenta_id
        validar_paginacion(desde, cantidad)
        filas = sesion.execute(
            _MIS_BOLSAS, {"cuenta": mi_cuenta, "desde": desde, "cantidad": cantidad}
        ).all()
    return [
        ResumenBolsa(f.id, f.nombre, f.estado, f.fecha_limite, f.parte, f.mi_estado)
        for f in filas
    ]


def movimientos_bolsa(
    sesion: Session,
    token: str,
    bolsa_id: UUID,
    desde: int,
    cantidad: int,
    ahora: datetime,
) -> list[EntradaHistorial]:
    """Mis aportes y devoluciones con la bolsa, con la forma del historial.

    SPEC 9.4: "devuelve solo los aportes y devoluciones entre quien pide y la
    bolsa". La transferencia final queda fuera aunque yo sea la cuenta
    objetivo.
    """
    with sesion.begin():
        _lectura_consistente(sesion)
        mi_cuenta = autenticar(sesion, token, ahora).cuenta_id
        bolsa = _bolsa_visible(sesion, bolsa_id, mi_cuenta)
        validar_paginacion(desde, cantidad)
        filas = sesion.execute(
            _MIS_MOVIMIENTOS,
            {
                "cuenta": mi_cuenta,
                "bolsa": bolsa.cuenta_id,
                "desde": desde,
                "cantidad": cantidad,
            },
        ).all()
    return [
        EntradaHistorial(f.tipo, f.contrapartida, f.monto, f.creado_en) for f in filas
    ]
