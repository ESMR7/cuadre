"""Invariantes de SPEC 4: la lista, cómo se corren, su detección y `make check`.

Las pruebas de detección (SPEC 10.5) arman un libro válido con SQL directo y
lo confirman, comprueban que no hay violaciones, lo dañan a propósito y
comprueban que la consulta lo reporta. Dejan la base inválida, así que llevan
`sin_invariantes`: el fixture solo vacía la base al terminar.

Por ahora hay detección de L1 a L4. Las de B6, B8, B9 y B10 se escriben
después de T14.
"""

import re
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, make_url, text
from sqlalchemy.orm import Session, sessionmaker

from app.db import invariantes
from app.db.invariantes import (
    AVISO_ERROR,
    INVARIANTES,
    Invariante,
    correr_invariantes,
    formatear_reporte,
    reportar,
    violaciones,
)
from tests.bd_prueba import borrar_base, exigir_invariantes, recrear_base
from tests.db.sql_directo import (
    crear_persona,
    ejecutar,
    insertar_clave,
    insertar_movimiento,
    insertar_transaccion,
    registrar_transaccion,
)

RUTA_SPEC = Path(__file__).resolve().parents[3] / "SPEC.md"

IDS = [f"L{n}" for n in range(1, 9)] + [f"B{n}" for n in range(1, 12)]

# Puerto 1: la conexión falla sin llegar a ningún servidor.
URL_INALCANZABLE = "postgresql+psycopg://usuario:secreta@127.0.0.1:1/cuadre"


def _normalizar(sql: str) -> str:
    return " ".join(sql.split())


def _ids(filas: list[tuple]) -> list:
    return [fila[0] for fila in filas]


def _sin_violaciones(motor: Engine) -> None:
    assert violaciones(correr_invariantes(motor)) == {}


def _libro_valido(bd: sessionmaker[Session]) -> tuple[int, int]:
    """Ana carga $100.000 y le transfiere $30.000 a Beto. Todo confirmado."""
    with bd() as s:
        crear_persona(s, "ana", "10000001")
        crear_persona(s, "beto", "10000002")
        carga = registrar_transaccion(s, "carga", "sistema", "ana", 100000)
        insertar_clave(s, "ana", operacion="cargar", transaccion_id=carga)
        transferencia = registrar_transaccion(s, "transferencia", "ana", "beto", 30000)
        insertar_clave(s, "ana", operacion="transferir", transaccion_id=transferencia)
        s.commit()
    return carga, transferencia


def _danar(bd: sessionmaker[Session], sql: str, **parametros: object) -> None:
    with bd() as s:
        ejecutar(s, sql, **parametros)
        s.commit()


def _fragmentos_de_url(motor: Engine) -> list[str]:
    url = motor.url
    fragmentos = [url.render_as_string(hide_password=False), "postgresql"]
    if url.password:
        fragmentos.append(str(url.password))
    return fragmentos


# --- la lista -----------------------------------------------------------------


def test_lista_tiene_exactamente_l1_a_l8_y_b1_a_b11_en_orden() -> None:
    assert [i.id for i in INVARIANTES] == IDS
    assert all(i.descripcion for i in INVARIANTES)


def test_sql_de_cada_invariante_coincide_con_spec() -> None:
    texto = RUTA_SPEC.read_text(encoding="utf-8")
    bloques = dict(
        re.findall(
            r"^\*\*([LB]\d+)\. .*?^```sql\n(.*?)^```", texto, re.DOTALL | re.MULTILINE
        )
    )
    assert sorted(bloques) == sorted(IDS)
    for invariante in INVARIANTES:
        assert _normalizar(invariante.sql) == _normalizar(bloques[invariante.id]), (
            invariante.id
        )


def test_cada_invariante_es_una_consulta_select_o_with() -> None:
    for invariante in INVARIANTES:
        assert invariante.sql.lstrip().upper().startswith(("SELECT", "WITH")), (
            invariante.id
        )


# --- cómo se corren -----------------------------------------------------------


def test_base_vacia_pasa_todas_las_invariantes(
    bd: sessionmaker[Session], motor_prueba: Engine
) -> None:
    resultados = correr_invariantes(motor_prueba)
    assert list(resultados) == IDS
    assert violaciones(resultados) == {}


def test_invariantes_corren_en_una_transaccion_repeatable_read_read_only(
    bd: sessionmaker[Session], motor_prueba: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    sql = (
        "SELECT current_setting('transaction_isolation'), "
        "current_setting('transaction_read_only'), now()"
    )
    monkeypatch.setattr(
        invariantes,
        "INVARIANTES",
        (Invariante("X1", "primera", sql), Invariante("X2", "segunda", sql)),
    )
    resultados = correr_invariantes(motor_prueba)
    [primera] = resultados["X1"]
    [segunda] = resultados["X2"]
    assert primera[:2] == ("repeatable read", "on")
    # now() es la hora de inicio de la transacción: igual en ambas consultas.
    assert primera == segunda


def test_correr_invariantes_filtra_por_ids(
    bd: sessionmaker[Session], motor_prueba: Engine
) -> None:
    assert list(correr_invariantes(motor_prueba, ["L3", "B1"])) == ["L3", "B1"]


def test_datos_validos_del_libro_pasan_todas_las_invariantes(
    bd: sessionmaker[Session], motor_prueba: Engine
) -> None:
    _libro_valido(bd)
    _sin_violaciones(motor_prueba)


# --- detección (SPEC 10.5) ----------------------------------------------------


@pytest.mark.sin_invariantes
def test_l1_detecta_transaccion_sin_dos_movimientos(
    bd: sessionmaker[Session], motor_prueba: Engine
) -> None:
    carga, _ = _libro_valido(bd)
    _sin_violaciones(motor_prueba)
    _danar(
        bd,
        "DELETE FROM movimientos WHERE transaccion_id = :id AND cuenta_id = 'sistema'",
        id=carga,
    )
    assert _ids(correr_invariantes(motor_prueba, ["L1"])["L1"]) == [carga]


@pytest.mark.sin_invariantes
def test_l2_detecta_pata_que_no_coincide_con_la_cabecera(
    bd: sessionmaker[Session], motor_prueba: Engine
) -> None:
    _, transferencia = _libro_valido(bd)
    _sin_violaciones(motor_prueba)
    _danar(
        bd,
        "UPDATE movimientos SET monto = monto + 1 "
        "WHERE transaccion_id = :id AND cuenta_id = 'beto'",
        id=transferencia,
    )
    resultados = correr_invariantes(motor_prueba, ["L1", "L2"])
    assert resultados["L1"] == []
    assert _ids(resultados["L2"]) == [transferencia]


@pytest.mark.sin_invariantes
def test_l3_detecta_saldo_distinto_de_sus_movimientos(
    bd: sessionmaker[Session], motor_prueba: Engine
) -> None:
    _libro_valido(bd)
    _sin_violaciones(motor_prueba)
    _danar(bd, "UPDATE cuentas SET saldo = saldo + 1 WHERE id = 'ana'")
    assert _ids(correr_invariantes(motor_prueba, ["L3"])["L3"]) == ["ana"]


@pytest.mark.sin_invariantes
def test_l4_detecta_suma_de_saldos_distinta_de_cero_sin_romper_l3(
    bd: sessionmaker[Session], motor_prueba: Engine
) -> None:
    """Una carga con una sola pata: el saldo de Ana cuadra con sus movimientos,
    pero el dinero salió de la nada. L3 no lo ve; L1, L2 y L4 sí."""
    with bd() as s:
        crear_persona(s, "ana", "10000001")
        s.commit()
    _sin_violaciones(motor_prueba)
    with bd() as s:
        carga = insertar_transaccion(s, "carga", "sistema", "ana", 1000)
        insertar_movimiento(s, carga, "ana", 1000)
        ejecutar(s, "UPDATE cuentas SET saldo = 1000 WHERE id = 'ana'")
        s.commit()
    resultados = correr_invariantes(motor_prueba, ["L1", "L2", "L3", "L4"])
    assert _ids(resultados["L1"]) == [carga]
    assert _ids(resultados["L2"]) == [carga]
    assert resultados["L3"] == []
    assert resultados["L4"] == [(1000,)]


# --- el fixture -------------------------------------------------------------


@pytest.mark.sin_invariantes
def test_exigir_invariantes_pasa_con_base_valida_y_falla_con_base_invalida(
    bd: sessionmaker[Session], motor_prueba: Engine
) -> None:
    _libro_valido(bd)
    exigir_invariantes(motor_prueba)
    _danar(bd, "UPDATE cuentas SET saldo = saldo + 1 WHERE id = 'ana'")
    with pytest.raises(AssertionError, match="L3") as error:
        exigir_invariantes(motor_prueba)
    mensaje = str(error.value)
    assert "ana" in mensaje
    for fragmento in _fragmentos_de_url(motor_prueba):
        assert fragmento not in mensaje


# --- el reporte de make check -------------------------------------------------


def test_reporte_imprime_una_linea_por_invariante_y_sale_con_cero(
    bd: sessionmaker[Session], motor_prueba: Engine, capsys: pytest.CaptureFixture
) -> None:
    _libro_valido(bd)
    assert reportar(motor_prueba) == 0
    salida = capsys.readouterr()
    lineas = salida.out.splitlines()
    assert [linea.split()[0] for linea in lineas[: len(IDS)]] == IDS
    assert all(linea.split()[1:3] == ["PASA", "0"] for linea in lineas[: len(IDS)])
    for fragmento in _fragmentos_de_url(motor_prueba):
        assert fragmento not in salida.out + salida.err


@pytest.mark.sin_invariantes
def test_reporte_sale_distinto_de_cero_y_lista_ids_si_falla(
    bd: sessionmaker[Session], motor_prueba: Engine, capsys: pytest.CaptureFixture
) -> None:
    _libro_valido(bd)
    _danar(bd, "UPDATE cuentas SET saldo = saldo + 1 WHERE id IN ('ana', 'beto')")
    assert reportar(motor_prueba) != 0
    lineas = {linea.split()[0]: linea for linea in capsys.readouterr().out.splitlines()}
    assert lineas["L3"].split() == ["L3", "FALLA", "2", "ana,", "beto"]
    assert lineas["L4"].split()[1:3] == ["FALLA", "1"]
    assert lineas["L1"].split()[1] == "PASA"


def test_reporte_limita_y_ordena_los_ids_mostrados() -> None:
    resultados = {
        "L1": [],
        "L3": [(f"c{n}", 1, 0) for n in (6, 2, 0, 5, 1, 4, 3)],
        "L7": [("ana", "c0ffee", "cargar")],
    }
    lineas = formatear_reporte(resultados, maximo_ids=5)
    assert lineas[0].split() == ["L1", "PASA", "0"]
    assert lineas[1].split() == ["L3", "FALLA", "7", "c0,", "c1,", "c2,", "c3,", "c4"]
    assert lineas[2].split() == ["L7", "FALLA", "1", "ana/c0ffee"]


def test_error_de_conexion_no_imprime_la_url(capsys: pytest.CaptureFixture) -> None:
    motor = create_engine(URL_INALCANZABLE)
    try:
        assert reportar(motor) == 2
    finally:
        motor.dispose()
    salida = capsys.readouterr()
    texto = salida.out + salida.err
    assert AVISO_ERROR in texto
    assert "OperationalError" in texto
    for fragmento in ("secreta", "usuario", "postgresql", "127.0.0.1"):
        assert fragmento not in texto


def test_base_sin_tablas_sale_con_dos_sin_imprimir_la_url(
    url_prueba: str, capsys: pytest.CaptureFixture
) -> None:
    url = make_url(url_prueba).set(database="cuadre_sin_tablas_test")
    url_texto = url.render_as_string(hide_password=False)
    recrear_base(url_texto)
    motor = create_engine(url)
    try:
        with motor.connect() as conexion:
            assert (
                conexion.execute(
                    text("SELECT count(*) FROM pg_tables WHERE schemaname = 'public'")
                ).scalar_one()
                == 0
            )
        assert reportar(motor) == 2
    finally:
        motor.dispose()
        borrar_base(url_texto)
    salida = capsys.readouterr()
    texto = salida.out + salida.err
    assert AVISO_ERROR in texto
    assert "ProgrammingError" in texto
    assert "cuentas" not in texto  # no se imprime el texto del error
    for fragmento in _fragmentos_de_url(motor):
        assert fragmento not in texto


def test_main_sin_database_url_sale_con_dos(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    def sin_url() -> Engine:
        raise RuntimeError("Falta la variable de entorno DATABASE_URL")

    monkeypatch.setattr(invariantes, "obtener_motor", sin_url)
    assert invariantes.main() == 2
    salida = capsys.readouterr()
    texto = salida.out + salida.err
    assert AVISO_ERROR in texto
    assert "RuntimeError" in texto
