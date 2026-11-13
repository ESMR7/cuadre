"""El esquema migrado coincide con SPEC 3.4 (T2). Solo consulta el catálogo."""

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from tests.bd_prueba import crear_cuenta_sistema, vaciar_tablas
from tests.db.sql_directo import ejecutar

TEXTO = "text"
ENTERO = "bigint"
FECHA = "timestamp with time zone"
UUID = "uuid"
BOOLEANO = "boolean"

# (columna, tipo, admite nulo), en el orden de SPEC 3.4.
COLUMNAS = {
    "cuentas": [
        ("id", TEXTO, False),
        ("tipo", TEXTO, False),
        ("saldo", ENTERO, False),
        ("creada_en", FECHA, False),
    ],
    "usuarios": [
        ("id", ENTERO, False),
        ("cedula", TEXTO, False),
        ("nombre_usuario", TEXTO, False),
        ("contrasena_hash", TEXTO, False),
        ("cuenta_id", TEXTO, False),
        ("creado_en", FECHA, False),
    ],
    "sesiones": [
        ("usuario_id", ENTERO, False),
        ("token_hash", TEXTO, False),
        ("creada_en", FECHA, False),
        ("expira_en", FECHA, False),
    ],
    "transacciones": [
        ("id", ENTERO, False),
        ("tipo", TEXTO, False),
        ("cuenta_origen_id", TEXTO, False),
        ("cuenta_destino_id", TEXTO, False),
        ("monto", ENTERO, False),
        ("creado_en", FECHA, False),
    ],
    "movimientos": [
        ("transaccion_id", ENTERO, False),
        ("cuenta_id", TEXTO, False),
        ("monto", ENTERO, False),
    ],
    "claves_idempotencia": [
        ("cuenta_solicitante_id", TEXTO, False),
        ("clave", UUID, False),
        ("operacion", TEXTO, False),
        ("hash_peticion", TEXTO, False),
        ("transaccion_id", ENTERO, True),
        ("creado_en", FECHA, False),
    ],
    "bolsas": [
        ("id", UUID, False),
        ("nombre", TEXTO, False),
        ("total", ENTERO, False),
        ("cuenta_id", TEXTO, False),
        ("creador_cuenta_id", TEXTO, False),
        ("cuenta_objetivo_id", TEXTO, False),
        ("transferir_al_vencer", BOOLEANO, False),
        ("fecha_limite", FECHA, False),
        ("estado", TEXTO, False),
        ("creada_en", FECHA, False),
    ],
    "participantes": [
        ("bolsa_id", UUID, False),
        ("cuenta_id", TEXTO, False),
        ("parte", ENTERO, False),
        ("estado", TEXTO, False),
    ],
}

MONTOS = {
    ("cuentas", "saldo"),
    ("transacciones", "monto"),
    ("movimientos", "monto"),
    ("bolsas", "total"),
    ("participantes", "parte"),
}

COLUMNAS_COLLATE_C = {
    ("cuentas", "id"),
    ("usuarios", "nombre_usuario"),
    ("usuarios", "cuenta_id"),
    ("transacciones", "cuenta_origen_id"),
    ("transacciones", "cuenta_destino_id"),
    ("movimientos", "cuenta_id"),
    ("claves_idempotencia", "cuenta_solicitante_id"),
    ("bolsas", "nombre"),
    ("bolsas", "cuenta_id"),
    ("bolsas", "creador_cuenta_id"),
    ("bolsas", "cuenta_objetivo_id"),
    ("participantes", "cuenta_id"),
}

RESTRICCIONES = {
    # Nombres fijados por SPEC 3.4.
    "pk_cuentas",
    "ck_cuentas_tipo",
    "ck_cuentas_formato_id",
    "ck_cuentas_saldo",
    "uq_usuarios_cedula",
    "ck_usuarios_cedula",
    "uq_usuarios_nombre",
    "ck_usuarios_nombre",
    "uq_usuarios_cuenta",
    "ck_usuarios_cuenta",
    "ck_sesiones_hash",
    "ck_sesiones_expira",
    "ck_transacciones_tipo",
    "ck_transacciones_monto",
    "ck_transacciones_cuentas_distintas",
    "ck_movimientos_monto",
    "ck_claves_solicitante",
    "ck_claves_operacion",
    "ck_claves_hash",
    "ck_bolsas_nombre",
    "ck_bolsas_total",
    "ck_bolsas_creador",
    "ck_bolsas_objetivo",
    "ck_bolsas_estado",
    "ck_bolsas_cuenta",
    "ck_bolsas_fecha",
    "ck_participantes_cuenta",
    "ck_participantes_parte",
    "ck_participantes_estado",
    # Nombres de la convención de T1 (SPEC 3.4 no los fija).
    "pk_usuarios",
    "pk_sesiones",
    "pk_transacciones",
    "pk_movimientos",
    "pk_claves_idempotencia",
    "pk_bolsas",
    "pk_participantes",
    "uq_sesiones_token_hash",
    "uq_bolsas_cuenta_id",
    "uq_claves_idempotencia_transaccion_id",
    "fk_usuarios_cuenta_id_cuentas",
    "fk_sesiones_usuario_id_usuarios",
    "fk_transacciones_cuenta_origen_id_cuentas",
    "fk_transacciones_cuenta_destino_id_cuentas",
    "fk_movimientos_transaccion_id_transacciones",
    "fk_movimientos_cuenta_id_cuentas",
    "fk_claves_idempotencia_cuenta_solicitante_id_cuentas",
    "fk_claves_idempotencia_transaccion_id_transacciones",
    "fk_bolsas_cuenta_id_cuentas",
    "fk_bolsas_creador_cuenta_id_cuentas",
    "fk_bolsas_cuenta_objetivo_id_cuentas",
    "fk_participantes_bolsa_id_bolsas",
    "fk_participantes_cuenta_id_cuentas",
}

# Índices que no respaldan una restricción: (tabla, único, columnas, condición).
INDICES = {
    "uq_aporte_unico": (
        "transacciones",
        True,
        ["cuenta_origen_id", "cuenta_destino_id"],
        "(tipo = 'aporte'::text)",
    ),
    "uq_devolucion_unica": (
        "transacciones",
        True,
        ["cuenta_origen_id", "cuenta_destino_id"],
        "(tipo = 'devolucion'::text)",
    ),
    "uq_transferencia_final_unica": (
        "transacciones",
        True,
        ["cuenta_origen_id"],
        "(tipo = 'transferencia_final'::text)",
    ),
    "ix_transacciones_origen_tipo": (
        "transacciones",
        False,
        ["cuenta_origen_id", "tipo"],
        None,
    ),
    "ix_transacciones_destino_tipo": (
        "transacciones",
        False,
        ["cuenta_destino_id", "tipo"],
        None,
    ),
    "ix_movimientos_cuenta": (
        "movimientos",
        False,
        ["cuenta_id", "transaccion_id"],
        None,
    ),
    "ix_participantes_cuenta": ("participantes", False, ["cuenta_id"], None),
    "ix_bolsas_vencimiento": (
        "bolsas",
        False,
        ["fecha_limite"],
        "(estado <> 'cerrada'::text)",
    ),
}

FILTRO_TABLAS = "table_schema = 'public' AND table_name <> 'alembic_version'"


def test_columnas_de_cada_tabla_son_exactas(bd: sessionmaker[Session]) -> None:
    with bd() as s:
        filas = ejecutar(
            s,
            "SELECT table_name, column_name, data_type, is_nullable = 'YES' "
            f"FROM information_schema.columns WHERE {FILTRO_TABLAS} "
            "ORDER BY table_name, ordinal_position",
        ).all()
    reales: dict[str, list[tuple[str, str, bool]]] = {}
    for tabla, columna, tipo, nula in filas:
        reales.setdefault(tabla, []).append((columna, tipo, nula))
    assert reales == COLUMNAS


def test_participantes_no_tiene_columna_decision(bd: sessionmaker[Session]) -> None:
    with bd() as s:
        cantidad = ejecutar(
            s,
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_name = 'participantes' AND column_name = 'decision'",
        ).scalar_one()
    assert cantidad == 0


def test_montos_y_saldos_son_bigint(bd: sessionmaker[Session]) -> None:
    with bd() as s:
        filas = ejecutar(
            s,
            "SELECT table_name, column_name, data_type "
            f"FROM information_schema.columns WHERE {FILTRO_TABLAS} "
            "AND column_name IN ('saldo', 'monto', 'total', 'parte')",
        ).all()
    assert {(t, c) for t, c, _ in filas} == MONTOS
    assert {tipo for _, _, tipo in filas} == {ENTERO}


def test_ninguna_columna_es_de_punto_flotante_ni_numeric(
    bd: sessionmaker[Session],
) -> None:
    with bd() as s:
        tipos = (
            ejecutar(
                s,
                "SELECT DISTINCT data_type FROM information_schema.columns "
                f"WHERE {FILTRO_TABLAS}",
            )
            .scalars()
            .all()
        )
    assert set(tipos) <= {TEXTO, ENTERO, FECHA, UUID, BOOLEANO}


def test_fechas_son_timestamptz_sin_default(bd: sessionmaker[Session]) -> None:
    with bd() as s:
        filas = ejecutar(
            s,
            "SELECT table_name, column_name, column_default "
            f"FROM information_schema.columns WHERE {FILTRO_TABLAS} "
            f"AND data_type = '{FECHA}'",
        ).all()
    assert {(t, c) for t, c, _ in filas} == {
        (tabla, columna)
        for tabla, columnas in COLUMNAS.items()
        for columna, tipo, _ in columnas
        if tipo == FECHA
    }
    assert len(filas) == 8
    assert all(default is None for _, _, default in filas)


def test_solo_saldo_e_id_de_bolsa_tienen_default(bd: sessionmaker[Session]) -> None:
    with bd() as s:
        filas = ejecutar(
            s,
            "SELECT table_name, column_name, column_default "
            f"FROM information_schema.columns WHERE {FILTRO_TABLAS} "
            "AND column_default IS NOT NULL",
        ).all()
    assert {(t, c, d) for t, c, d in filas} == {
        ("cuentas", "saldo", "0"),
        ("bolsas", "id", "gen_random_uuid()"),
    }


def test_ids_identity_son_generated_always(bd: sessionmaker[Session]) -> None:
    with bd() as s:
        filas = ejecutar(
            s,
            "SELECT table_name, column_name, identity_generation "
            f"FROM information_schema.columns WHERE {FILTRO_TABLAS} "
            "AND is_identity = 'YES'",
        ).all()
    assert set(filas) == {
        ("usuarios", "id", "ALWAYS"),
        ("transacciones", "id", "ALWAYS"),
    }


def test_no_existen_tipos_enum(bd: sessionmaker[Session]) -> None:
    with bd() as s:
        cantidad = ejecutar(
            s, "SELECT count(*) FROM pg_type WHERE typtype = 'e'"
        ).scalar_one()
    assert cantidad == 0


def test_ids_de_cuenta_usan_collate_c(bd: sessionmaker[Session]) -> None:
    with bd() as s:
        filas = ejecutar(
            s,
            "SELECT table_name, column_name FROM information_schema.columns "
            f"WHERE {FILTRO_TABLAS} AND collation_name = 'C'",
        ).all()
    assert set(map(tuple, filas)) == COLUMNAS_COLLATE_C


def test_restricciones_tienen_los_nombres_del_spec(bd: sessionmaker[Session]) -> None:
    with bd() as s:
        nombres = (
            ejecutar(
                s,
                "SELECT c.conname FROM pg_constraint c "
                "JOIN pg_class t ON t.oid = c.conrelid "
                "JOIN pg_namespace n ON n.oid = t.relnamespace "
                "WHERE n.nspname = 'public' AND t.relname <> 'alembic_version'",
            )
            .scalars()
            .all()
        )
    assert len(nombres) == len(set(nombres))
    assert set(nombres) == RESTRICCIONES


def test_indices_existen_con_sus_columnas_y_condicion(
    bd: sessionmaker[Session],
) -> None:
    with bd() as s:
        filas = ejecutar(
            s,
            "SELECT i.relname, t.relname, x.indisunique, "
            "ARRAY(SELECT a.attname FROM unnest(x.indkey) WITH ORDINALITY k(n, o) "
            "JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = k.n "
            "ORDER BY k.o), "
            "pg_get_expr(x.indpred, x.indrelid) "
            "FROM pg_index x "
            "JOIN pg_class i ON i.oid = x.indexrelid "
            "JOIN pg_class t ON t.oid = x.indrelid "
            "JOIN pg_namespace n ON n.oid = t.relnamespace "
            "WHERE n.nspname = 'public' AND t.relname <> 'alembic_version' "
            "AND NOT EXISTS (SELECT 1 FROM pg_constraint c "
            "WHERE c.conindid = x.indexrelid)",
        ).all()
    reales = {
        nombre: (tabla, unico, list(columnas), condicion)
        for nombre, tabla, unico, columnas, condicion in filas
    }
    assert reales == INDICES


def test_no_hay_triggers_de_usuario(bd: sessionmaker[Session]) -> None:
    with bd() as s:
        cantidad = ejecutar(
            s,
            "SELECT count(*) FROM pg_trigger t "
            "JOIN pg_class c ON c.oid = t.tgrelid "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND NOT t.tgisinternal",
        ).scalar_one()
    assert cantidad == 0


def test_fixture_recrea_la_cuenta_de_sistema_tras_vaciar(
    bd: sessionmaker[Session], motor_prueba: Engine
) -> None:
    vaciar_tablas(motor_prueba)
    crear_cuenta_sistema(motor_prueba)
    with bd() as s:
        filas = ejecutar(s, "SELECT id, tipo, saldo FROM cuentas").all()
    assert [tuple(f) for f in filas] == [("sistema", "sistema", 0)]


def test_cada_prueba_empieza_con_la_cuenta_de_sistema(
    bd: sessionmaker[Session],
) -> None:
    with bd() as s:
        filas = ejecutar(s, "SELECT id, tipo, saldo FROM cuentas").all()
    assert [tuple(f) for f in filas] == [("sistema", "sistema", 0)]
