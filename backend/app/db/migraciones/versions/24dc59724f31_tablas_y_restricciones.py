"""tablas y restricciones

Revision ID: 24dc59724f31
Revises:
Create Date: 2026-11-13 10:24:13.414705

Escrita a mano desde SPEC 3.4: Alembic no detecta bien los CHECK, los índices
parciales ni la colación. Todo nombre va en op.f() para que la convención de
nombres de los modelos no lo reescriba.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "24dc59724f31"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ID_CUENTA = sa.Text(collation="C")
FECHA = sa.DateTime(timezone=True)
HASH_SHA256 = "'^[0-9a-f]{64}$'"


def formato_personal(columna: str) -> str:
    """Formato personal de SPEC 3.4: sin la segunda condición, 'sistema' pasaría."""
    return f"{columna} ~ '^[a-z0-9_]{{3,30}}$' AND {columna} <> 'sistema'"


def fk_cuenta(tabla: str, columna: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [columna], ["cuentas.id"], name=op.f(f"fk_{tabla}_{columna}_cuentas")
    )


def upgrade() -> None:
    op.create_table(
        "cuentas",
        sa.Column("id", ID_CUENTA, nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column(
            "saldo", sa.BigInteger(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("creada_en", FECHA, nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cuentas")),
        sa.CheckConstraint(
            "tipo IN ('personal', 'bolsa', 'sistema')", name=op.f("ck_cuentas_tipo")
        ),
        sa.CheckConstraint(
            "(tipo = 'personal' AND id ~ '^[a-z0-9_]{3,30}$' AND id <> 'sistema') "
            "OR (tipo = 'bolsa' AND id ~ '^bolsa-[a-z0-9_]{3,30}-[a-z0-9_]{1,40}$') "
            "OR (tipo = 'sistema' AND id = 'sistema')",
            name=op.f("ck_cuentas_formato_id"),
        ),
        sa.CheckConstraint(
            "(tipo = 'sistema' AND saldo <= 0) OR (tipo <> 'sistema' AND saldo >= 0)",
            name=op.f("ck_cuentas_saldo"),
        ),
    )

    op.create_table(
        "usuarios",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("cedula", sa.Text(), nullable=False),
        sa.Column("nombre_usuario", ID_CUENTA, nullable=False),
        sa.Column("contrasena_hash", sa.Text(), nullable=False),
        sa.Column("cuenta_id", ID_CUENTA, nullable=False),
        sa.Column("creado_en", FECHA, nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usuarios")),
        # Orden de creación: nombre antes que cuenta. Un nombre repetido viola
        # ambas y PostgreSQL reporta el primer índice.
        sa.UniqueConstraint("cedula", name=op.f("uq_usuarios_cedula")),
        sa.UniqueConstraint("nombre_usuario", name=op.f("uq_usuarios_nombre")),
        sa.UniqueConstraint("cuenta_id", name=op.f("uq_usuarios_cuenta")),
        sa.CheckConstraint("cedula ~ '^[0-9]{5,10}$'", name=op.f("ck_usuarios_cedula")),
        sa.CheckConstraint(
            formato_personal("nombre_usuario"), name=op.f("ck_usuarios_nombre")
        ),
        sa.CheckConstraint(
            "cuenta_id = nombre_usuario", name=op.f("ck_usuarios_cuenta")
        ),
        fk_cuenta("usuarios", "cuenta_id"),
    )

    op.create_table(
        "sesiones",
        sa.Column("usuario_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("creada_en", FECHA, nullable=False),
        sa.Column("expira_en", FECHA, nullable=False),
        sa.PrimaryKeyConstraint("usuario_id", name=op.f("pk_sesiones")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_sesiones_token_hash")),
        sa.CheckConstraint(
            f"token_hash ~ {HASH_SHA256}", name=op.f("ck_sesiones_hash")
        ),
        sa.CheckConstraint("expira_en > creada_en", name=op.f("ck_sesiones_expira")),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuarios.id"],
            name=op.f("fk_sesiones_usuario_id_usuarios"),
        ),
    )

    op.create_table(
        "transacciones",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("cuenta_origen_id", ID_CUENTA, nullable=False),
        sa.Column("cuenta_destino_id", ID_CUENTA, nullable=False),
        sa.Column("monto", sa.BigInteger(), nullable=False),
        sa.Column("creado_en", FECHA, nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transacciones")),
        sa.CheckConstraint(
            "tipo IN ('carga', 'transferencia', 'aporte', 'devolucion', "
            "'transferencia_final')",
            name=op.f("ck_transacciones_tipo"),
        ),
        sa.CheckConstraint("monto > 0", name=op.f("ck_transacciones_monto")),
        sa.CheckConstraint(
            "cuenta_origen_id <> cuenta_destino_id",
            name=op.f("ck_transacciones_cuentas_distintas"),
        ),
        fk_cuenta("transacciones", "cuenta_origen_id"),
        fk_cuenta("transacciones", "cuenta_destino_id"),
    )

    op.create_table(
        "movimientos",
        sa.Column("transaccion_id", sa.BigInteger(), nullable=False),
        sa.Column("cuenta_id", ID_CUENTA, nullable=False),
        sa.Column("monto", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint(
            "transaccion_id", "cuenta_id", name=op.f("pk_movimientos")
        ),
        sa.CheckConstraint("monto <> 0", name=op.f("ck_movimientos_monto")),
        sa.ForeignKeyConstraint(
            ["transaccion_id"],
            ["transacciones.id"],
            name=op.f("fk_movimientos_transaccion_id_transacciones"),
        ),
        fk_cuenta("movimientos", "cuenta_id"),
    )

    op.create_table(
        "claves_idempotencia",
        sa.Column("cuenta_solicitante_id", ID_CUENTA, nullable=False),
        sa.Column("clave", sa.Uuid(), nullable=False),
        sa.Column("operacion", sa.Text(), nullable=False),
        sa.Column("hash_peticion", sa.Text(), nullable=False),
        sa.Column("transaccion_id", sa.BigInteger(), nullable=True),
        sa.Column("creado_en", FECHA, nullable=False),
        sa.PrimaryKeyConstraint(
            "cuenta_solicitante_id", "clave", name=op.f("pk_claves_idempotencia")
        ),
        sa.UniqueConstraint(
            "transaccion_id", name=op.f("uq_claves_idempotencia_transaccion_id")
        ),
        sa.CheckConstraint(
            formato_personal("cuenta_solicitante_id"),
            name=op.f("ck_claves_solicitante"),
        ),
        sa.CheckConstraint(
            "operacion IN ('cargar', 'transferir', 'aportar', 'retirarse')",
            name=op.f("ck_claves_operacion"),
        ),
        sa.CheckConstraint(
            f"hash_peticion ~ {HASH_SHA256}", name=op.f("ck_claves_hash")
        ),
        fk_cuenta("claves_idempotencia", "cuenta_solicitante_id"),
        sa.ForeignKeyConstraint(
            ["transaccion_id"],
            ["transacciones.id"],
            name=op.f("fk_claves_idempotencia_transaccion_id_transacciones"),
        ),
    )

    op.create_table(
        "bolsas",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("nombre", ID_CUENTA, nullable=False),
        sa.Column("total", sa.BigInteger(), nullable=False),
        sa.Column("cuenta_id", ID_CUENTA, nullable=False),
        sa.Column("creador_cuenta_id", ID_CUENTA, nullable=False),
        sa.Column("cuenta_objetivo_id", ID_CUENTA, nullable=False),
        sa.Column("transferir_al_vencer", sa.Boolean(), nullable=False),
        sa.Column("fecha_limite", FECHA, nullable=False),
        sa.Column("estado", sa.Text(), nullable=False),
        sa.Column("creada_en", FECHA, nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bolsas")),
        sa.UniqueConstraint("cuenta_id", name=op.f("uq_bolsas_cuenta_id")),
        sa.CheckConstraint(
            "nombre ~ '^[a-z0-9_]{1,40}$'", name=op.f("ck_bolsas_nombre")
        ),
        sa.CheckConstraint("total >= 10000", name=op.f("ck_bolsas_total")),
        sa.CheckConstraint(
            formato_personal("creador_cuenta_id"), name=op.f("ck_bolsas_creador")
        ),
        sa.CheckConstraint(
            formato_personal("cuenta_objetivo_id"), name=op.f("ck_bolsas_objetivo")
        ),
        sa.CheckConstraint(
            "estado IN ('abierta', 'cancelada', 'liquidando', 'cerrada')",
            name=op.f("ck_bolsas_estado"),
        ),
        sa.CheckConstraint(
            "cuenta_id = 'bolsa-' || creador_cuenta_id || '-' || nombre",
            name=op.f("ck_bolsas_cuenta"),
        ),
        sa.CheckConstraint("fecha_limite > creada_en", name=op.f("ck_bolsas_fecha")),
        fk_cuenta("bolsas", "cuenta_id"),
        fk_cuenta("bolsas", "creador_cuenta_id"),
        fk_cuenta("bolsas", "cuenta_objetivo_id"),
    )

    op.create_table(
        "participantes",
        sa.Column("bolsa_id", sa.Uuid(), nullable=False),
        sa.Column("cuenta_id", ID_CUENTA, nullable=False),
        sa.Column("parte", sa.BigInteger(), nullable=False),
        sa.Column("estado", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("bolsa_id", "cuenta_id", name=op.f("pk_participantes")),
        sa.CheckConstraint(
            formato_personal("cuenta_id"), name=op.f("ck_participantes_cuenta")
        ),
        sa.CheckConstraint("parte > 0", name=op.f("ck_participantes_parte")),
        sa.CheckConstraint(
            "estado IN ('pendiente', 'pagado', 'por_confirmar', 'retirado')",
            name=op.f("ck_participantes_estado"),
        ),
        sa.ForeignKeyConstraint(
            ["bolsa_id"], ["bolsas.id"], name=op.f("fk_participantes_bolsa_id_bolsas")
        ),
        fk_cuenta("participantes", "cuenta_id"),
    )

    # Índices únicos parciales: un aporte y una devolución por participante y
    # bolsa, y una sola transferencia final por bolsa.
    op.create_index(
        op.f("uq_aporte_unico"),
        "transacciones",
        ["cuenta_origen_id", "cuenta_destino_id"],
        unique=True,
        postgresql_where=sa.text("tipo = 'aporte'"),
    )
    op.create_index(
        op.f("uq_devolucion_unica"),
        "transacciones",
        ["cuenta_origen_id", "cuenta_destino_id"],
        unique=True,
        postgresql_where=sa.text("tipo = 'devolucion'"),
    )
    op.create_index(
        op.f("uq_transferencia_final_unica"),
        "transacciones",
        ["cuenta_origen_id"],
        unique=True,
        postgresql_where=sa.text("tipo = 'transferencia_final'"),
    )
    op.create_index(
        op.f("ix_transacciones_origen_tipo"),
        "transacciones",
        ["cuenta_origen_id", "tipo"],
    )
    op.create_index(
        op.f("ix_transacciones_destino_tipo"),
        "transacciones",
        ["cuenta_destino_id", "tipo"],
    )
    op.create_index(
        op.f("ix_movimientos_cuenta"), "movimientos", ["cuenta_id", "transaccion_id"]
    )
    op.create_index(op.f("ix_participantes_cuenta"), "participantes", ["cuenta_id"])
    op.create_index(
        op.f("ix_bolsas_vencimiento"),
        "bolsas",
        ["fecha_limite"],
        postgresql_where=sa.text("estado <> 'cerrada'"),
    )

    # SPEC 1.3: la única cuenta de sistema la crea la migración. now() es el
    # momento en que se crea el sistema; no es un DEFAULT de la columna.
    op.execute(
        "INSERT INTO cuentas (id, tipo, saldo, creada_en) "
        "VALUES ('sistema', 'sistema', 0, now())"
    )


def downgrade() -> None:
    # Borrar las tablas borra sus índices y la cuenta de sistema.
    for tabla in (
        "participantes",
        "bolsas",
        "claves_idempotencia",
        "movimientos",
        "transacciones",
        "sesiones",
        "usuarios",
        "cuentas",
    ):
        op.drop_table(tabla)
