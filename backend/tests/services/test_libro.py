"""Servicio del libro: bloqueo, lectura fresca y escritura (SPEC 2.4 y 10.3)."""

import re
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.modelos import Cuenta
from app.domain.errores import NoEncontrado
from app.domain.libro import LibroDescuadrado
from app.services.idempotencia import ClaveSinTransaccion, respuesta_guardada
from app.services.libro import bloquear_cuentas, registrar_transaccion
from app.services.nucleo import cargar, transferir
from tests.db.sql_directo import crear_bolsa, insertar_clave, insertar_participante
from tests.services.apoyo_libro import AHORA, capturar_sql, contar, crear_usuario

FOR_NO_KEY = re.compile(r"FOR NO KEY UPDATE", re.IGNORECASE)
FOR_UPDATE_A_SECAS = re.compile(r"(?<!NO KEY )FOR UPDATE", re.IGNORECASE)


def ids_bloqueados(sentencias, candidatos) -> list[str]:
    """Id de cuenta de cada SELECT ... FOR NO KEY UPDATE, en orden de ejecución."""
    bloqueados = []
    for sql, parametros in sentencias:
        if FOR_NO_KEY.search(sql) and "cuentas" in sql:
            # Solo los parámetros del id: el del tipo puede valer "sistema".
            valores = [v for k, v in parametros.items() if k.startswith("id")]
            encontrados = [v for v in valores if v in candidatos]
            assert len(encontrados) == 1, (sql, parametros)
            bloqueados.append(encontrados[0])
    return bloqueados


def test_orden_de_python_coincide_con_collate_c_de_postgresql(bd):
    # _ (0x5F) va entre los dígitos y las minúsculas en orden de bytes; una
    # intercalación lingüística (en_US) lo ignoraría y daría otro orden.
    ids = ["abc", "ab_", "ab0", "_ab", "0ab", "zzz", "a_b", "aab", "sistema"]
    with bd() as sesion, sesion.begin():
        for id_ in ids:
            if id_ != "sistema":
                sesion.execute(
                    text(
                        "INSERT INTO cuentas (id, tipo, saldo, creada_en) "
                        "VALUES (:id, 'personal', 0, :ahora)"
                    ),
                    {"id": id_, "ahora": AHORA},
                )
        en_postgres = (
            sesion.execute(
                text("SELECT id FROM cuentas WHERE id = ANY(:ids) ORDER BY id"),
                {"ids": ids},
            )
            .scalars()
            .all()
        )
        sesion.rollback()
    assert en_postgres == sorted(ids)


def test_lectura_fresca_con_populate_existing(bd):
    token_ana = crear_usuario(bd, "ana", "1000001")
    crear_usuario(bd, "beto", "1000002")
    with bd() as sesion:
        cargar(sesion, token_ana, uuid4(), 100_000, AHORA)

    with bd() as sesion_1, sesion_1.begin():
        cuenta = sesion_1.get(Cuenta, "ana")
        assert cuenta.saldo == 100_000
        with bd() as sesion_2:
            transferir(sesion_2, token_ana, uuid4(), "beto", 60_000, AHORA)
        bloqueadas = bloquear_cuentas(sesion_1, {"ana": "personal"})
        assert bloqueadas["ana"] is cuenta
        assert bloqueadas["ana"].saldo == 40_000


def test_transferir_bloquea_una_sentencia_por_cuenta_ascendente_tras_la_clave(
    bd, motor_prueba
):
    token_zeta = crear_usuario(bd, "zeta", "1000001")
    crear_usuario(bd, "beto", "1000002")
    with bd() as sesion:
        cargar(sesion, token_zeta, uuid4(), 1_000, AHORA)

    with capturar_sql(motor_prueba) as sentencias, bd() as sesion:
        transferir(sesion, token_zeta, uuid4(), "beto", 500, AHORA)

    assert ids_bloqueados(sentencias, {"zeta", "beto"}) == ["beto", "zeta"]
    textos = [sql for sql, _ in sentencias]
    reserva = next(
        i
        for i, sql in enumerate(textos)
        if "INSERT INTO claves_idempotencia" in sql and "ON CONFLICT" in sql
    )
    primer_bloqueo = next(i for i, sql in enumerate(textos) if FOR_NO_KEY.search(sql))
    assert reserva < primer_bloqueo
    assert not [
        sql for sql in textos if "cuentas" in sql and FOR_UPDATE_A_SECAS.search(sql)
    ]


def test_cargar_bloquea_sistema_y_la_cuenta_en_orden_ascendente(bd, motor_prueba):
    # "ana" < "sistema" < "zeta" con COLLATE "C": sistema no siempre va primero.
    token_ana = crear_usuario(bd, "ana", "1000001")
    token_zeta = crear_usuario(bd, "zeta", "1000002")
    with capturar_sql(motor_prueba) as sentencias, bd() as sesion:
        cargar(sesion, token_ana, uuid4(), 100, AHORA)
        cargar(sesion, token_zeta, uuid4(), 100, AHORA)
    assert ids_bloqueados(sentencias, {"ana", "zeta", "sistema"}) == [
        "ana",
        "sistema",
        "sistema",
        "zeta",
    ]
    textos = [sql for sql, _ in sentencias]
    assert not [
        sql for sql in textos if "cuentas" in sql and FOR_UPDATE_A_SECAS.search(sql)
    ]


def test_bloquear_cuentas_exige_el_tipo_esperado(bd):
    crear_usuario(bd, "ana", "1000001")
    with bd() as sesion, sesion.begin(), pytest.raises(NoEncontrado):
        bloquear_cuentas(sesion, {"ana": "personal", "sistema": "personal"})


def test_bloquear_cuentas_inexistente_da_no_encontrado(bd):
    with bd() as sesion, sesion.begin(), pytest.raises(NoEncontrado):
        bloquear_cuentas(sesion, {"nadie": "personal"})


def test_registrar_transaccion_con_tipos_invalidos_no_deja_rastro(bd):
    crear_usuario(bd, "ana", "1000001")
    crear_usuario(bd, "beto", "1000002")
    with bd() as sesion, pytest.raises(LibroDescuadrado), sesion.begin():
        cuentas = bloquear_cuentas(sesion, {"ana": "personal", "beto": "personal"})
        registrar_transaccion(
            sesion, "carga", cuentas["ana"], cuentas["beto"], 100, AHORA
        )
    assert contar(bd, "transacciones") == 0
    assert contar(bd, "movimientos") == 0


def test_respuesta_guardada_sin_transaccion_lanza_error_interno(bd):
    crear_usuario(bd, "ana", "1000001")
    with bd() as sesion, sesion.begin():
        clave = insertar_clave(
            sesion, "ana", operacion="cargar", hash_peticion="b" * 64
        )
        with pytest.raises(ClaveSinTransaccion):
            respuesta_guardada(sesion, "ana", clave, "b" * 64)
        sesion.rollback()
    assert contar(bd, "claves_idempotencia") == 0


def test_bolsa_valida_para_pruebas_de_destino(bd):
    # Control del dato que usa test_nucleo: una bolsa válida no rompe invariantes.
    crear_usuario(bd, "ana", "1000001")
    crear_usuario(bd, "beto", "1000002")
    with bd() as sesion, sesion.begin():
        bolsa = crear_bolsa(sesion, "ana")
        insertar_participante(sesion, bolsa, "ana", 5000)
        insertar_participante(sesion, bolsa, "beto", 5000)
