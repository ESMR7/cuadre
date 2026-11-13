"""Modelos de la base (SPEC 3.4). Reflejan la migración, que es la fuente.

Sin relaciones ni lógica. Los nombres que fija el SPEC van en conv() para que
la convención no los reescriba: sin él, ck_claves_solicitante se volvería
ck_claves_idempotencia_solicitante. Las PK y FK salen de la convención.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    MetaData,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql.elements import conv

# SPEC 3.1: toda restricción tiene nombre con prefijo pk_, ck_, uq_, fk_ o ix_.
CONVENCION_NOMBRES = {
    "pk": "pk_%(table_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
}

ID_CUENTA = Text(collation="C")
FECHA = DateTime(timezone=True)
HASH_SHA256 = "'^[0-9a-f]{64}$'"


def formato_personal(columna: str) -> str:
    """Formato personal de SPEC 3.4: sin la segunda condición, 'sistema' pasaría."""
    return f"{columna} ~ '^[a-z0-9_]{{3,30}}$' AND {columna} <> 'sistema'"


def check(sql: str, nombre: str) -> CheckConstraint:
    return CheckConstraint(sql, name=conv(nombre))


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENCION_NOMBRES)


class Cuenta(Base):
    __tablename__ = "cuentas"
    __table_args__ = (
        check("tipo IN ('personal', 'bolsa', 'sistema')", "ck_cuentas_tipo"),
        check(
            "(tipo = 'personal' AND id ~ '^[a-z0-9_]{3,30}$' AND id <> 'sistema') "
            "OR (tipo = 'bolsa' AND id ~ '^bolsa-[a-z0-9_]{3,30}-[a-z0-9_]{1,40}$') "
            "OR (tipo = 'sistema' AND id = 'sistema')",
            "ck_cuentas_formato_id",
        ),
        check(
            "(tipo = 'sistema' AND saldo <= 0) OR (tipo <> 'sistema' AND saldo >= 0)",
            "ck_cuentas_saldo",
        ),
    )

    id: Mapped[str] = mapped_column(ID_CUENTA, primary_key=True)
    tipo: Mapped[str] = mapped_column(Text)
    # Solo el servicio del libro lo cambia, con saldo = saldo + :delta en SQL.
    saldo: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    creada_en: Mapped[datetime] = mapped_column(FECHA)


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = (
        UniqueConstraint("cedula", name=conv("uq_usuarios_cedula")),
        UniqueConstraint("nombre_usuario", name=conv("uq_usuarios_nombre")),
        UniqueConstraint("cuenta_id", name=conv("uq_usuarios_cuenta")),
        check("cedula ~ '^[0-9]{5,10}$'", "ck_usuarios_cedula"),
        check(formato_personal("nombre_usuario"), "ck_usuarios_nombre"),
        check("cuenta_id = nombre_usuario", "ck_usuarios_cuenta"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    cedula: Mapped[str] = mapped_column(Text)
    nombre_usuario: Mapped[str] = mapped_column(ID_CUENTA)
    contrasena_hash: Mapped[str] = mapped_column(Text)
    cuenta_id: Mapped[str] = mapped_column(ID_CUENTA, ForeignKey("cuentas.id"))
    creado_en: Mapped[datetime] = mapped_column(FECHA)


class Sesion(Base):
    __tablename__ = "sesiones"
    __table_args__ = (
        UniqueConstraint("token_hash"),
        check(f"token_hash ~ {HASH_SHA256}", "ck_sesiones_hash"),
        check("expira_en > creada_en", "ck_sesiones_expira"),
    )

    usuario_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("usuarios.id"), primary_key=True
    )
    token_hash: Mapped[str] = mapped_column(Text)
    creada_en: Mapped[datetime] = mapped_column(FECHA)
    expira_en: Mapped[datetime] = mapped_column(FECHA)


class Transaccion(Base):
    __tablename__ = "transacciones"
    __table_args__ = (
        check(
            "tipo IN ('carga', 'transferencia', 'aporte', 'devolucion', "
            "'transferencia_final')",
            "ck_transacciones_tipo",
        ),
        check("monto > 0", "ck_transacciones_monto"),
        check(
            "cuenta_origen_id <> cuenta_destino_id",
            "ck_transacciones_cuentas_distintas",
        ),
        Index(
            conv("uq_aporte_unico"),
            "cuenta_origen_id",
            "cuenta_destino_id",
            unique=True,
            postgresql_where=text("tipo = 'aporte'"),
        ),
        Index(
            conv("uq_devolucion_unica"),
            "cuenta_origen_id",
            "cuenta_destino_id",
            unique=True,
            postgresql_where=text("tipo = 'devolucion'"),
        ),
        Index(
            conv("uq_transferencia_final_unica"),
            "cuenta_origen_id",
            unique=True,
            postgresql_where=text("tipo = 'transferencia_final'"),
        ),
        Index(conv("ix_transacciones_origen_tipo"), "cuenta_origen_id", "tipo"),
        Index(conv("ix_transacciones_destino_tipo"), "cuenta_destino_id", "tipo"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    tipo: Mapped[str] = mapped_column(Text)
    cuenta_origen_id: Mapped[str] = mapped_column(ID_CUENTA, ForeignKey("cuentas.id"))
    cuenta_destino_id: Mapped[str] = mapped_column(ID_CUENTA, ForeignKey("cuentas.id"))
    monto: Mapped[int] = mapped_column(BigInteger)
    creado_en: Mapped[datetime] = mapped_column(FECHA)


class Movimiento(Base):
    __tablename__ = "movimientos"
    __table_args__ = (
        check("monto <> 0", "ck_movimientos_monto"),
        Index(conv("ix_movimientos_cuenta"), "cuenta_id", "transaccion_id"),
    )

    transaccion_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("transacciones.id"), primary_key=True
    )
    cuenta_id: Mapped[str] = mapped_column(
        ID_CUENTA, ForeignKey("cuentas.id"), primary_key=True
    )
    monto: Mapped[int] = mapped_column(BigInteger)


class ClaveIdempotencia(Base):
    __tablename__ = "claves_idempotencia"
    __table_args__ = (
        UniqueConstraint("transaccion_id"),
        check(formato_personal("cuenta_solicitante_id"), "ck_claves_solicitante"),
        check(
            "operacion IN ('cargar', 'transferir', 'aportar', 'retirarse')",
            "ck_claves_operacion",
        ),
        check(f"hash_peticion ~ {HASH_SHA256}", "ck_claves_hash"),
    )

    cuenta_solicitante_id: Mapped[str] = mapped_column(
        ID_CUENTA, ForeignKey("cuentas.id"), primary_key=True
    )
    clave: Mapped[UUID] = mapped_column(primary_key=True)
    operacion: Mapped[str] = mapped_column(Text)
    hash_peticion: Mapped[str] = mapped_column(Text)
    # Nula solo si la operación no movió dinero (retirarse sin pago).
    transaccion_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("transacciones.id")
    )
    creado_en: Mapped[datetime] = mapped_column(FECHA)


class Bolsa(Base):
    __tablename__ = "bolsas"
    __table_args__ = (
        UniqueConstraint("cuenta_id"),
        check("nombre ~ '^[a-z0-9_]{1,40}$'", "ck_bolsas_nombre"),
        check("total >= 10000", "ck_bolsas_total"),
        check(formato_personal("creador_cuenta_id"), "ck_bolsas_creador"),
        check(formato_personal("cuenta_objetivo_id"), "ck_bolsas_objetivo"),
        check(
            "estado IN ('abierta', 'cancelada', 'liquidando', 'cerrada')",
            "ck_bolsas_estado",
        ),
        check(
            "cuenta_id = 'bolsa-' || creador_cuenta_id || '-' || nombre",
            "ck_bolsas_cuenta",
        ),
        check("fecha_limite > creada_en", "ck_bolsas_fecha"),
        Index(
            conv("ix_bolsas_vencimiento"),
            "fecha_limite",
            postgresql_where=text("estado <> 'cerrada'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    nombre: Mapped[str] = mapped_column(ID_CUENTA)
    total: Mapped[int] = mapped_column(BigInteger)
    cuenta_id: Mapped[str] = mapped_column(ID_CUENTA, ForeignKey("cuentas.id"))
    creador_cuenta_id: Mapped[str] = mapped_column(ID_CUENTA, ForeignKey("cuentas.id"))
    cuenta_objetivo_id: Mapped[str] = mapped_column(ID_CUENTA, ForeignKey("cuentas.id"))
    transferir_al_vencer: Mapped[bool] = mapped_column()
    fecha_limite: Mapped[datetime] = mapped_column(FECHA)
    estado: Mapped[str] = mapped_column(Text)
    creada_en: Mapped[datetime] = mapped_column(FECHA)


class Participante(Base):
    __tablename__ = "participantes"
    __table_args__ = (
        check(formato_personal("cuenta_id"), "ck_participantes_cuenta"),
        check("parte > 0", "ck_participantes_parte"),
        check(
            "estado IN ('pendiente', 'pagado', 'por_confirmar', 'retirado')",
            "ck_participantes_estado",
        ),
        Index(conv("ix_participantes_cuenta"), "cuenta_id"),
    )

    bolsa_id: Mapped[UUID] = mapped_column(ForeignKey("bolsas.id"), primary_key=True)
    cuenta_id: Mapped[str] = mapped_column(
        ID_CUENTA, ForeignKey("cuentas.id"), primary_key=True
    )
    parte: Mapped[int] = mapped_column(BigInteger)
    estado: Mapped[str] = mapped_column(Text)
