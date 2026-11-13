"""Infraestructura de la base de pruebas (SPEC 10.2 y 10.4)."""

import pytest
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import Configuracion, exigir
from tests.bd_prueba import (
    POOL_PRUEBAS,
    RUTA_ALEMBIC_INI,
    borrar_base,
    exigir_base_de_prueba,
    recrear_base,
    vaciar_tablas,
)

# NotImplementedError hereda de RuntimeError: por eso cada prueba de la guarda
# exige además el mensaje, para no pasar con una firma vacía.
GUARDA = "debe terminar en _test"

# Puerto 1: si alguna función se conectara antes de la guarda, fallaría con
# OperationalError y no con RuntimeError.
URL_DESARROLLO = "postgresql+psycopg://usuario:secreta@127.0.0.1:1/cuadre"


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://u:p@localhost:5432/cuadre",
        "postgresql+psycopg://u:p@localhost:5432/cuadre_testing",
        "postgresql+psycopg://u:p@localhost:5432/test_cuadre",
        "postgresql+psycopg://u:p@localhost:5432",
        'postgresql+psycopg://u:p@localhost:5432/cua"dre_test',
    ],
)
def test_guarda_rechaza_base_sin_sufijo_test(url: str) -> None:
    with pytest.raises(RuntimeError, match=GUARDA):
        exigir_base_de_prueba(url)


def test_error_de_guarda_no_incluye_la_url() -> None:
    with pytest.raises(RuntimeError, match=GUARDA) as error:
        exigir_base_de_prueba(URL_DESARROLLO)
    mensaje = str(error.value)
    assert "cuadre" in mensaje
    assert "secreta" not in mensaje
    assert "usuario" not in mensaje
    assert "postgresql" not in mensaje


def test_guarda_acepta_base_con_sufijo_test() -> None:
    url = exigir_base_de_prueba("postgresql+psycopg://u:p@localhost:5432/cuadre_test")
    assert url.database == "cuadre_test"


def test_funciones_destructivas_respetan_la_guarda() -> None:
    with pytest.raises(RuntimeError, match=GUARDA):
        recrear_base(URL_DESARROLLO)
    with pytest.raises(RuntimeError, match=GUARDA):
        borrar_base(URL_DESARROLLO)
    motor = create_engine(URL_DESARROLLO)
    try:
        with pytest.raises(RuntimeError, match=GUARDA):
            vaciar_tablas(motor)
    finally:
        motor.dispose()


def test_falta_variable_menciona_solo_el_nombre() -> None:
    configuracion = Configuracion(_env_file=None, database_url=None)
    with pytest.raises(RuntimeError, match="DATABASE_URL") as error:
        exigir("DATABASE_URL", configuracion)
    assert "DATABASE_URL" in str(error.value)


def test_ruta_alembic_ini_es_absoluta_y_existe() -> None:
    assert RUTA_ALEMBIC_INI.is_absolute()
    assert RUTA_ALEMBIC_INI.is_file()


def test_conecta_a_cuadre_test(bd: sessionmaker[Session]) -> None:
    with bd() as sesion:
        nombre = sesion.execute(text("SELECT current_database()")).scalar_one()
    assert nombre == "cuadre_test"


def test_base_de_prueba_esta_en_head(motor_prueba: Engine) -> None:
    script = ScriptDirectory.from_config(Config(str(RUTA_ALEMBIC_INI)))
    with motor_prueba.connect() as conexion:
        actual = MigrationContext.configure(conexion).get_current_revision()
    assert actual == script.get_current_head()


def test_motor_usa_read_committed(bd: sessionmaker[Session]) -> None:
    with bd() as sesion:
        nivel = sesion.execute(text("SHOW transaction_isolation")).scalar_one()
    assert nivel == "read committed"


def test_pool_de_pruebas_tiene_al_menos_20_conexiones(motor_prueba: Engine) -> None:
    assert motor_prueba.pool.size() >= POOL_PRUEBAS


def test_vaciar_tablas_deja_tablas_vacias(motor_prueba: Engine) -> None:
    with motor_prueba.begin() as conexion:
        conexion.execute(text("CREATE TABLE prueba_padre (id int PRIMARY KEY)"))
        conexion.execute(
            text(
                "CREATE TABLE prueba_hija (id int PRIMARY KEY, "
                "padre_id int NOT NULL REFERENCES prueba_padre (id))"
            )
        )
        conexion.execute(text("INSERT INTO prueba_padre VALUES (1)"))
        conexion.execute(text("INSERT INTO prueba_hija VALUES (1, 1)"))
    try:
        vaciar_tablas(motor_prueba)
        with motor_prueba.connect() as conexion:
            for tabla in ("prueba_padre", "prueba_hija"):
                cantidad = conexion.execute(
                    text(f"SELECT count(*) FROM {tabla}")
                ).scalar_one()
                assert cantidad == 0
    finally:
        with motor_prueba.begin() as conexion:
            conexion.execute(text("DROP TABLE IF EXISTS prueba_hija, prueba_padre"))
