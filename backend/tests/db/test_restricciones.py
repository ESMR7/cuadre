"""Cada restricción de SPEC 3.4 rechaza lo que debe (T2).

Cada prueba parte de filas válidas y cambia un solo valor. Se comprueba el
nombre de la restricción en el error, no solo que hubo un error. PostgreSQL
evalúa los CHECK en orden alfabético y antes que los índices únicos y las
llaves foráneas; los datos de cada prueba violan una sola restricción.
Nada se confirma: la sesión se revierte al salir.
"""

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session, sessionmaker

from tests.db.sql_directo import (
    AHORA,
    CHECK,
    FORANEA,
    GENERADA_SIEMPRE,
    NO_NULA,
    UNICA,
    crear_bolsa,
    crear_persona,
    cuenta_de_bolsa,
    ejecutar,
    esperar_violacion,
    insertar_bolsa,
    insertar_clave,
    insertar_cuenta,
    insertar_movimiento,
    insertar_participante,
    insertar_sesion,
    insertar_transaccion,
    insertar_usuario,
    violar,
)

# --- cuentas ---------------------------------------------------------------


def test_pk_cuentas_rechaza_id_repetido(bd: sessionmaker[Session]) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        esperar_violacion(lambda: insertar_cuenta(s, "ana"), "pk_cuentas", UNICA)


@pytest.mark.parametrize(
    ("id", "tipo"),
    [
        ("Ana", "personal"),
        ("ana\n", "personal"),
        ("an", "personal"),
        ("sistema", "personal"),
        ("bolsa-ana-mi-viaje", "bolsa"),
        ("bolsa-ana", "bolsa"),
        ("ana", "bolsa"),
        ("central", "sistema"),
        # Un tipo desconocido no cumple ninguna rama del formato, que se
        # evalúa antes que ck_cuentas_tipo por orden alfabético.
        ("ana", "ahorro"),
    ],
)
def test_ck_cuentas_formato_id_rechaza_id_invalido_para_su_tipo(
    bd: sessionmaker[Session], id: str, tipo: str
) -> None:
    with bd() as s:
        esperar_violacion(
            lambda: insertar_cuenta(s, id, tipo=tipo), "ck_cuentas_formato_id", CHECK
        )


def test_ck_cuentas_tipo_solo_admite_los_tres_tipos(
    bd: sessionmaker[Session],
) -> None:
    # No se puede violar sola (ver la prueba anterior): se verifica su definición.
    with bd() as s:
        definicion = ejecutar(
            s,
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname = 'ck_cuentas_tipo'",
        ).scalar_one()
    for tipo in ("'personal'", "'bolsa'", "'sistema'"):
        assert tipo in definicion
    assert "tipo" in definicion


@pytest.mark.parametrize(
    ("id", "tipo", "saldo"),
    [
        ("ana", "personal", -1),
        ("bolsa-ana-viaje", "bolsa", -1),
        ("sistema", "sistema", 1),
    ],
)
def test_ck_cuentas_saldo_rechaza_saldo_con_signo_prohibido(
    bd: sessionmaker[Session], id: str, tipo: str, saldo: int
) -> None:
    with bd() as s:
        esperar_violacion(
            lambda: insertar_cuenta(s, id, tipo=tipo, saldo=saldo),
            "ck_cuentas_saldo",
            CHECK,
        )


# --- usuarios --------------------------------------------------------------


def test_uq_usuarios_cedula_rechaza_cedula_repetida(bd: sessionmaker[Session]) -> None:
    with bd() as s:
        crear_persona(s, "ana", "12345")
        insertar_cuenta(s, "beto")
        esperar_violacion(
            lambda: insertar_usuario(s, "beto", "12345"), "uq_usuarios_cedula", UNICA
        )


@pytest.mark.parametrize("cedula", ["1234", "12345678901", "12a45", "12345\n"])
def test_ck_usuarios_cedula_rechaza_formato_invalido(
    bd: sessionmaker[Session], cedula: str
) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        esperar_violacion(
            lambda: insertar_usuario(s, "ana", cedula), "ck_usuarios_cedula", CHECK
        )


def test_uq_usuarios_nombre_rechaza_nombre_repetido(bd: sessionmaker[Session]) -> None:
    with bd() as s:
        crear_persona(s, "ana", "12345")
        esperar_violacion(
            lambda: insertar_usuario(s, "ana", "67890"), "uq_usuarios_nombre", UNICA
        )


@pytest.mark.parametrize("nombre", ["Ana", "ana\n", "sistema", "an", "ana-maria"])
def test_ck_usuarios_nombre_rechaza_nombre_invalido(
    bd: sessionmaker[Session], nombre: str
) -> None:
    # cuenta_id = nombre: ck_usuarios_cuenta se cumple y la cuenta no hace
    # falta, porque los CHECK se evalúan antes que la llave foránea.
    with bd() as s:
        esperar_violacion(
            lambda: insertar_usuario(s, nombre, "12345"), "ck_usuarios_nombre", CHECK
        )


def test_ck_usuarios_cuenta_rechaza_cuenta_distinta_del_nombre(
    bd: sessionmaker[Session],
) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        insertar_cuenta(s, "beto")
        esperar_violacion(
            lambda: insertar_usuario(s, "ana", "12345", cuenta_id="beto"),
            "ck_usuarios_cuenta",
            CHECK,
        )


def test_fk_usuarios_rechaza_usuario_sin_cuenta(bd: sessionmaker[Session]) -> None:
    with bd() as s:
        esperar_violacion(
            lambda: insertar_usuario(s, "ana", "12345"),
            "fk_usuarios_cuenta_id_cuentas",
            FORANEA,
        )


@pytest.mark.parametrize(
    "sql",
    [
        (
            "INSERT INTO usuarios (id, cedula, nombre_usuario, contrasena_hash, "
            "cuenta_id, creado_en) VALUES (1, '12345', 'ana', 'h', 'ana', :ahora)"
        ),
        (
            "INSERT INTO transacciones (id, tipo, cuenta_origen_id, "
            "cuenta_destino_id, monto, creado_en) "
            "VALUES (1, 'transferencia', 'ana', 'beto', 1, :ahora)"
        ),
    ],
)
def test_ids_identity_no_admiten_valor_explicito(
    bd: sessionmaker[Session], sql: str
) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        insertar_cuenta(s, "beto")
        error = violar(lambda: ejecutar(s, sql, ahora=AHORA))
    assert error.sqlstate == GENERADA_SIEMPRE


# --- sesiones --------------------------------------------------------------


def test_pk_sesiones_permite_una_sola_sesion_por_usuario(
    bd: sessionmaker[Session],
) -> None:
    with bd() as s:
        usuario = crear_persona(s, "ana", "12345")
        insertar_sesion(s, usuario)
        esperar_violacion(
            lambda: insertar_sesion(s, usuario, token_hash="b" * 64),
            "pk_sesiones",
            UNICA,
        )


def test_uq_sesiones_token_hash_rechaza_hash_repetido(
    bd: sessionmaker[Session],
) -> None:
    with bd() as s:
        ana = crear_persona(s, "ana", "12345")
        beto = crear_persona(s, "beto", "67890")
        insertar_sesion(s, ana)
        esperar_violacion(
            lambda: insertar_sesion(s, beto), "uq_sesiones_token_hash", UNICA
        )


@pytest.mark.parametrize("token_hash", ["A" * 64, "a" * 63, "a" * 65, "g" * 64])
def test_ck_sesiones_hash_rechaza_formato_invalido(
    bd: sessionmaker[Session], token_hash: str
) -> None:
    with bd() as s:
        usuario = crear_persona(s, "ana", "12345")
        esperar_violacion(
            lambda: insertar_sesion(s, usuario, token_hash=token_hash),
            "ck_sesiones_hash",
            CHECK,
        )


def test_ck_sesiones_expira_rechaza_expiracion_no_posterior(
    bd: sessionmaker[Session],
) -> None:
    with bd() as s:
        usuario = crear_persona(s, "ana", "12345")
        esperar_violacion(
            lambda: insertar_sesion(s, usuario, creada_en=AHORA, expira_en=AHORA),
            "ck_sesiones_expira",
            CHECK,
        )


def test_fk_sesiones_rechaza_usuario_inexistente(bd: sessionmaker[Session]) -> None:
    with bd() as s:
        esperar_violacion(
            lambda: insertar_sesion(s, 999), "fk_sesiones_usuario_id_usuarios", FORANEA
        )


# --- transacciones ---------------------------------------------------------


def test_ck_transacciones_tipo_rechaza_tipo_desconocido(
    bd: sessionmaker[Session],
) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        insertar_cuenta(s, "beto")
        esperar_violacion(
            lambda: insertar_transaccion(s, "regalo", "ana", "beto"),
            "ck_transacciones_tipo",
            CHECK,
        )


@pytest.mark.parametrize("monto", [0, -1])
def test_ck_transacciones_monto_rechaza_monto_no_positivo(
    bd: sessionmaker[Session], monto: int
) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        insertar_cuenta(s, "beto")
        esperar_violacion(
            lambda: insertar_transaccion(s, "transferencia", "ana", "beto", monto),
            "ck_transacciones_monto",
            CHECK,
        )


def test_ck_transacciones_cuentas_distintas_rechaza_mismo_origen_y_destino(
    bd: sessionmaker[Session],
) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        esperar_violacion(
            lambda: insertar_transaccion(s, "transferencia", "ana", "ana"),
            "ck_transacciones_cuentas_distintas",
            CHECK,
        )


def test_uq_aporte_unico_rechaza_segundo_aporte(bd: sessionmaker[Session]) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        crear_bolsa(s, "ana")
        bolsa = cuenta_de_bolsa("ana", "viaje")
        insertar_transaccion(s, "aporte", "ana", bolsa)
        esperar_violacion(
            lambda: insertar_transaccion(s, "aporte", "ana", bolsa),
            "uq_aporte_unico",
            UNICA,
        )


def test_uq_devolucion_unica_rechaza_segunda_devolucion(
    bd: sessionmaker[Session],
) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        crear_bolsa(s, "ana")
        bolsa = cuenta_de_bolsa("ana", "viaje")
        insertar_transaccion(s, "devolucion", bolsa, "ana")
        esperar_violacion(
            lambda: insertar_transaccion(s, "devolucion", bolsa, "ana"),
            "uq_devolucion_unica",
            UNICA,
        )


def test_uq_transferencia_final_unica_rechaza_segunda_transferencia_final(
    bd: sessionmaker[Session],
) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        insertar_cuenta(s, "beto")
        crear_bolsa(s, "ana")
        bolsa = cuenta_de_bolsa("ana", "viaje")
        insertar_transaccion(s, "transferencia_final", bolsa, "ana")
        # Aunque el destino sea otro: el cierre es único por bolsa.
        esperar_violacion(
            lambda: insertar_transaccion(s, "transferencia_final", bolsa, "beto"),
            "uq_transferencia_final_unica",
            UNICA,
        )


def test_transferencias_repetidas_entre_el_mismo_par_se_aceptan(
    bd: sessionmaker[Session],
) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        insertar_cuenta(s, "beto")
        insertar_transaccion(s, "transferencia", "ana", "beto")
        insertar_transaccion(s, "transferencia", "ana", "beto")
        cantidad = ejecutar(s, "SELECT count(*) FROM transacciones").scalar_one()
    assert cantidad == 2


def test_aporte_y_devolucion_del_mismo_participante_se_aceptan(
    bd: sessionmaker[Session],
) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        insertar_cuenta(s, "beto")
        crear_bolsa(s, "ana")
        bolsa = cuenta_de_bolsa("ana", "viaje")
        insertar_transaccion(s, "aporte", "ana", bolsa)
        insertar_transaccion(s, "aporte", "beto", bolsa)
        insertar_transaccion(s, "devolucion", bolsa, "ana")
        insertar_transaccion(s, "devolucion", bolsa, "beto")
        cantidad = ejecutar(s, "SELECT count(*) FROM transacciones").scalar_one()
    assert cantidad == 4


def test_transferencia_final_de_bolsas_distintas_se_acepta(
    bd: sessionmaker[Session],
) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        crear_bolsa(s, "ana", "viaje")
        crear_bolsa(s, "ana", "cena")
        insertar_transaccion(
            s, "transferencia_final", cuenta_de_bolsa("ana", "viaje"), "ana"
        )
        insertar_transaccion(
            s, "transferencia_final", cuenta_de_bolsa("ana", "cena"), "ana"
        )
        cantidad = ejecutar(s, "SELECT count(*) FROM transacciones").scalar_one()
    assert cantidad == 2


@pytest.mark.parametrize(
    ("origen", "destino", "restriccion"),
    [
        ("zoe", "ana", "fk_transacciones_cuenta_origen_id_cuentas"),
        ("ana", "zoe", "fk_transacciones_cuenta_destino_id_cuentas"),
    ],
)
def test_fk_transacciones_rechaza_cuenta_inexistente(
    bd: sessionmaker[Session], origen: str, destino: str, restriccion: str
) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        esperar_violacion(
            lambda: insertar_transaccion(s, "transferencia", origen, destino),
            restriccion,
            FORANEA,
        )


# --- movimientos -----------------------------------------------------------


def test_pk_movimientos_rechaza_dos_patas_sobre_la_misma_cuenta(
    bd: sessionmaker[Session],
) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        insertar_cuenta(s, "beto")
        transaccion = insertar_transaccion(s, "transferencia", "ana", "beto")
        insertar_movimiento(s, transaccion, "ana", -1000)
        esperar_violacion(
            lambda: insertar_movimiento(s, transaccion, "ana", 1000),
            "pk_movimientos",
            UNICA,
        )


def test_ck_movimientos_monto_rechaza_monto_cero(bd: sessionmaker[Session]) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        insertar_cuenta(s, "beto")
        transaccion = insertar_transaccion(s, "transferencia", "ana", "beto")
        esperar_violacion(
            lambda: insertar_movimiento(s, transaccion, "ana", 0),
            "ck_movimientos_monto",
            CHECK,
        )


def test_fk_movimientos_rechaza_transaccion_inexistente(
    bd: sessionmaker[Session],
) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        esperar_violacion(
            lambda: insertar_movimiento(s, 999, "ana", 1000),
            "fk_movimientos_transaccion_id_transacciones",
            FORANEA,
        )


def test_fk_movimientos_rechaza_cuenta_inexistente(
    bd: sessionmaker[Session],
) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        insertar_cuenta(s, "beto")
        transaccion = insertar_transaccion(s, "transferencia", "ana", "beto")
        esperar_violacion(
            lambda: insertar_movimiento(s, transaccion, "zoe", 1000),
            "fk_movimientos_cuenta_id_cuentas",
            FORANEA,
        )


# --- claves_idempotencia ---------------------------------------------------


def test_pk_claves_idempotencia_rechaza_clave_repetida(
    bd: sessionmaker[Session],
) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        clave = insertar_clave(s, "ana")
        esperar_violacion(
            lambda: insertar_clave(s, "ana", clave=clave),
            "pk_claves_idempotencia",
            UNICA,
        )


def test_misma_clave_de_dos_solicitantes_se_acepta(bd: sessionmaker[Session]) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        insertar_cuenta(s, "beto")
        clave = insertar_clave(s, "ana")
        insertar_clave(s, "beto", clave=clave)
        cantidad = ejecutar(s, "SELECT count(*) FROM claves_idempotencia").scalar_one()
    assert cantidad == 2


@pytest.mark.parametrize("solicitante", ["sistema", "bolsa-ana-viaje", "Ana"])
def test_ck_claves_solicitante_exige_formato_personal(
    bd: sessionmaker[Session], solicitante: str
) -> None:
    with bd() as s:
        esperar_violacion(
            lambda: insertar_clave(s, solicitante), "ck_claves_solicitante", CHECK
        )


def test_ck_claves_operacion_rechaza_operacion_desconocida(
    bd: sessionmaker[Session],
) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        esperar_violacion(
            lambda: insertar_clave(s, "ana", operacion="confirmar"),
            "ck_claves_operacion",
            CHECK,
        )


@pytest.mark.parametrize("hash_peticion", ["A" * 64, "a" * 63, ""])
def test_ck_claves_hash_rechaza_formato_invalido(
    bd: sessionmaker[Session], hash_peticion: str
) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        esperar_violacion(
            lambda: insertar_clave(s, "ana", hash_peticion=hash_peticion),
            "ck_claves_hash",
            CHECK,
        )


def test_uq_claves_transaccion_rechaza_dos_claves_con_la_misma_transaccion(
    bd: sessionmaker[Session],
) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        insertar_cuenta(s, "beto")
        transaccion = insertar_transaccion(s, "transferencia", "ana", "beto")
        insertar_clave(s, "ana", transaccion_id=transaccion)
        esperar_violacion(
            lambda: insertar_clave(s, "ana", transaccion_id=transaccion),
            "uq_claves_idempotencia_transaccion_id",
            UNICA,
        )


def test_claves_admiten_varias_sin_transaccion(bd: sessionmaker[Session]) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        insertar_clave(s, "ana", operacion="retirarse")
        insertar_clave(s, "ana", operacion="retirarse")
        cantidad = ejecutar(
            s, "SELECT count(*) FROM claves_idempotencia WHERE transaccion_id IS NULL"
        ).scalar_one()
    assert cantidad == 2


def test_fk_claves_rechaza_solicitante_inexistente(bd: sessionmaker[Session]) -> None:
    with bd() as s:
        esperar_violacion(
            lambda: insertar_clave(s, "zoe"),
            "fk_claves_idempotencia_cuenta_solicitante_id_cuentas",
            FORANEA,
        )


def test_fk_claves_rechaza_transaccion_inexistente(bd: sessionmaker[Session]) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        esperar_violacion(
            lambda: insertar_clave(s, "ana", transaccion_id=999),
            "fk_claves_idempotencia_transaccion_id_transacciones",
            FORANEA,
        )


# --- bolsas ----------------------------------------------------------------


def test_pk_bolsas_rechaza_id_repetido(bd: sessionmaker[Session]) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        id = crear_bolsa(s, "ana", "viaje")
        insertar_cuenta(s, cuenta_de_bolsa("ana", "cena"), tipo="bolsa")
        esperar_violacion(
            lambda: insertar_bolsa(s, "ana", "cena", id=id), "pk_bolsas", UNICA
        )


@pytest.mark.parametrize("nombre", ["Viaje", "mi-viaje", "", "a" * 41, "viaje\n"])
def test_ck_bolsas_nombre_rechaza_nombre_invalido(
    bd: sessionmaker[Session], nombre: str
) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        esperar_violacion(
            lambda: insertar_bolsa(s, "ana", nombre), "ck_bolsas_nombre", CHECK
        )


def test_ck_bolsas_total_rechaza_total_bajo_el_minimo(
    bd: sessionmaker[Session],
) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        esperar_violacion(
            lambda: insertar_bolsa(s, "ana", total=9999), "ck_bolsas_total", CHECK
        )


def test_uq_bolsas_cuenta_rechaza_dos_bolsas_con_la_misma_cuenta(
    bd: sessionmaker[Session],
) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        crear_bolsa(s, "ana", "viaje")
        esperar_violacion(
            lambda: insertar_bolsa(s, "ana", "viaje"), "uq_bolsas_cuenta_id", UNICA
        )


@pytest.mark.parametrize("creador", ["sistema", "Ana"])
def test_ck_bolsas_creador_exige_formato_personal(
    bd: sessionmaker[Session], creador: str
) -> None:
    # La cuenta de la bolsa se arma con el creador: ck_bolsas_cuenta se cumple.
    with bd() as s:
        insertar_cuenta(s, "ana")
        esperar_violacion(
            lambda: insertar_bolsa(s, creador, objetivo="ana"),
            "ck_bolsas_creador",
            CHECK,
        )


@pytest.mark.parametrize("objetivo", ["sistema", "bolsa-ana-cena", "Ana"])
def test_ck_bolsas_objetivo_exige_formato_personal(
    bd: sessionmaker[Session], objetivo: str
) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        esperar_violacion(
            lambda: insertar_bolsa(s, "ana", objetivo=objetivo),
            "ck_bolsas_objetivo",
            CHECK,
        )


@pytest.mark.parametrize("cuenta_id", ["bolsa-ana-cena", "bolsa-beto-viaje", "ana"])
def test_ck_bolsas_cuenta_exige_id_derivado_de_creador_y_nombre(
    bd: sessionmaker[Session], cuenta_id: str
) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        esperar_violacion(
            lambda: insertar_bolsa(s, "ana", "viaje", cuenta_id=cuenta_id),
            "ck_bolsas_cuenta",
            CHECK,
        )


def test_ck_bolsas_fecha_rechaza_fecha_limite_no_posterior(
    bd: sessionmaker[Session],
) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        esperar_violacion(
            lambda: insertar_bolsa(s, "ana", creada_en=AHORA, fecha_limite=AHORA),
            "ck_bolsas_fecha",
            CHECK,
        )


def test_ck_bolsas_estado_rechaza_estado_desconocido(
    bd: sessionmaker[Session],
) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        esperar_violacion(
            lambda: insertar_bolsa(s, "ana", estado="vencida"),
            "ck_bolsas_estado",
            CHECK,
        )


def test_bolsas_exigen_elegir_transferir_al_vencer(bd: sessionmaker[Session]) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        insertar_cuenta(s, cuenta_de_bolsa("ana", "viaje"), tipo="bolsa")
        error = violar(
            lambda: ejecutar(
                s,
                "INSERT INTO bolsas (nombre, total, cuenta_id, creador_cuenta_id, "
                "cuenta_objetivo_id, fecha_limite, estado, creada_en) VALUES "
                "('viaje', 10000, 'bolsa-ana-viaje', 'ana', 'ana', :limite, "
                "'abierta', :ahora)",
                limite=AHORA.replace(year=2027),
                ahora=AHORA,
            )
        )
    assert error.sqlstate == NO_NULA
    assert error.diag.column_name == "transferir_al_vencer"


@pytest.mark.parametrize(
    ("faltante", "restriccion"),
    [
        ("cuenta", "fk_bolsas_cuenta_id_cuentas"),
        ("creador", "fk_bolsas_creador_cuenta_id_cuentas"),
        ("objetivo", "fk_bolsas_cuenta_objetivo_id_cuentas"),
    ],
)
def test_fk_bolsas_rechaza_cuenta_inexistente(
    bd: sessionmaker[Session], faltante: str, restriccion: str
) -> None:
    with bd() as s:
        if faltante != "creador":
            insertar_cuenta(s, "ana")
        if faltante != "objetivo":
            insertar_cuenta(s, "beto")
        if faltante != "cuenta":
            insertar_cuenta(s, cuenta_de_bolsa("ana", "viaje"), tipo="bolsa")
        esperar_violacion(
            lambda: insertar_bolsa(s, "ana", "viaje", objetivo="beto"),
            restriccion,
            FORANEA,
        )


# --- participantes ---------------------------------------------------------


def test_pk_participantes_rechaza_participante_repetido(
    bd: sessionmaker[Session],
) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        bolsa = crear_bolsa(s, "ana")
        insertar_participante(s, bolsa, "ana")
        esperar_violacion(
            lambda: insertar_participante(s, bolsa, "ana"), "pk_participantes", UNICA
        )


@pytest.mark.parametrize("cuenta_id", ["sistema", "bolsa-ana-viaje", "Ana"])
def test_ck_participantes_cuenta_exige_formato_personal(
    bd: sessionmaker[Session], cuenta_id: str
) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        bolsa = crear_bolsa(s, "ana")
        esperar_violacion(
            lambda: insertar_participante(s, bolsa, cuenta_id),
            "ck_participantes_cuenta",
            CHECK,
        )


@pytest.mark.parametrize("parte", [0, -1])
def test_ck_participantes_parte_rechaza_parte_no_positiva(
    bd: sessionmaker[Session], parte: int
) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        bolsa = crear_bolsa(s, "ana")
        esperar_violacion(
            lambda: insertar_participante(s, bolsa, "ana", parte=parte),
            "ck_participantes_parte",
            CHECK,
        )


def test_ck_participantes_estado_rechaza_estado_desconocido(
    bd: sessionmaker[Session],
) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        bolsa = crear_bolsa(s, "ana")
        esperar_violacion(
            lambda: insertar_participante(s, bolsa, "ana", estado="aceptado"),
            "ck_participantes_estado",
            CHECK,
        )


def test_fk_participantes_rechaza_bolsa_inexistente(
    bd: sessionmaker[Session],
) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        esperar_violacion(
            lambda: insertar_participante(s, uuid4(), "ana"),
            "fk_participantes_bolsa_id_bolsas",
            FORANEA,
        )


def test_fk_participantes_rechaza_cuenta_inexistente(
    bd: sessionmaker[Session],
) -> None:
    with bd() as s:
        insertar_cuenta(s, "ana")
        bolsa = crear_bolsa(s, "ana")
        esperar_violacion(
            lambda: insertar_participante(s, bolsa, "zoe"),
            "fk_participantes_cuenta_id_cuentas",
            FORANEA,
        )


# --- control positivo ------------------------------------------------------


def test_filas_validas_en_todas_las_tablas_se_aceptan(
    bd: sessionmaker[Session],
) -> None:
    """Las restricciones no son más estrictas que el SPEC."""
    with bd() as s:
        ana = crear_persona(s, "ana", "12345")
        crear_persona(s, "beto_2", "9876543210")
        insertar_sesion(s, ana, token_hash="0123456789abcdef" * 4)
        transferencia = insertar_transaccion(s, "transferencia", "ana", "beto_2", 500)
        insertar_movimiento(s, transferencia, "ana", -500)
        insertar_movimiento(s, transferencia, "beto_2", 500)
        insertar_clave(s, "ana", operacion="transferir", transaccion_id=transferencia)
        nombre_largo = "a" * 40
        bolsa = crear_bolsa(
            s, "beto_2", nombre_largo, objetivo="ana", transferir_al_vencer=False
        )
        insertar_participante(s, bolsa, "ana", parte=5000, estado="pagado")
        insertar_participante(s, bolsa, "beto_2", parte=5000, estado="por_confirmar")
        aporte = insertar_transaccion(
            s, "aporte", "ana", cuenta_de_bolsa("beto_2", nombre_largo), 5000
        )
        insertar_clave(s, "ana", operacion="aportar", transaccion_id=aporte)
        insertar_clave(s, "beto_2", operacion="retirarse")
        for tabla, esperado in [
            ("cuentas", 4),  # incluida la de sistema
            ("usuarios", 2),
            ("sesiones", 1),
            ("transacciones", 2),
            ("movimientos", 2),
            ("claves_idempotencia", 3),
            ("bolsas", 1),
            ("participantes", 2),
        ]:
            cantidad = ejecutar(s, f"SELECT count(*) FROM {tabla}").scalar_one()
            assert cantidad == esperado, tabla
