"""Registro (SPEC 5.2) contra PostgreSQL real."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.modelos import Cuenta, Usuario
from app.domain.errores import RegistroRechazado
from app.services.seguridad import verificar_contrasena
from app.services.usuarios import UsuarioRegistrado, registrar

AHORA = datetime(2026, 11, 13, 15, 0, tzinfo=UTC)
CONTRASENA = "clave-segura-1"


def registrar_en(bd, nombre="ana", cedula="1234567", contrasena=CONTRASENA):
    with bd() as sesion:
        return registrar(sesion, nombre, cedula, contrasena, AHORA)


def contar(bd, modelo) -> int:
    with bd() as sesion:
        return sesion.scalar(select(func.count()).select_from(modelo))


def test_registrar_crea_cuenta_personal_con_saldo_cero_y_usuario(
    bd: sessionmaker[Session],
):
    registrar_en(bd)
    with bd() as sesion:
        cuenta = sesion.get(Cuenta, "ana")
        usuario = sesion.scalars(select(Usuario)).one()
        assert (cuenta.tipo, cuenta.saldo, cuenta.creada_en) == (
            "personal",
            0,
            AHORA,
        )
        assert usuario.nombre_usuario == "ana"
        assert usuario.cuenta_id == "ana"
        assert usuario.creado_en == AHORA
        assert verificar_contrasena(CONTRASENA, usuario.contrasena_hash)


def test_registrar_respuesta_no_incluye_cedula_ni_hash(bd: sessionmaker[Session]):
    respuesta = registrar_en(bd)
    assert respuesta == UsuarioRegistrado(nombre_usuario="ana", creado_en=AHORA)
    assert set(vars(respuesta)) == {"nombre_usuario", "creado_en"}


def test_registrar_hash_guardado_no_contiene_la_contrasena(
    bd: sessionmaker[Session],
):
    registrar_en(bd)
    with bd() as sesion:
        guardado = sesion.scalar(select(Usuario.contrasena_hash))
    assert guardado.startswith("scrypt$")
    assert CONTRASENA not in guardado


def test_nombre_repetido_da_registro_rechazado(bd: sessionmaker[Session]):
    registrar_en(bd)
    with pytest.raises(RegistroRechazado):
        registrar_en(bd, cedula="7654321")
    assert contar(bd, Usuario) == 1


def test_cedula_repetida_da_registro_rechazado(bd: sessionmaker[Session]):
    registrar_en(bd)
    with pytest.raises(RegistroRechazado):
        registrar_en(bd, nombre="beto")
    # La transacción revirtió: no queda la cuenta de beto sin usuario.
    with bd() as sesion:
        assert sesion.get(Cuenta, "beto") is None
    assert contar(bd, Usuario) == 1


def test_registro_rechazado_no_encadena_el_error_ni_incluye_la_cedula(
    bd: sessionmaker[Session],
):
    registrar_en(bd, cedula="98765432")
    with pytest.raises(RegistroRechazado) as info:
        registrar_en(bd, nombre="beto", cedula="98765432")
    error = info.value
    assert error.__cause__ is None
    assert error.__suppress_context__ is True
    assert "98765432" not in str(error)
    assert error.codigo == "registro_rechazado"


def test_otra_violacion_de_integridad_se_propaga(bd: sessionmaker[Session]):
    # ck_usuarios_cedula: no está en la lista de restricciones traducidas.
    with pytest.raises(IntegrityError) as info:
        registrar_en(bd, cedula="abc")
    assert info.value.orig.diag.constraint_name == "ck_usuarios_cedula"
    with bd() as sesion:
        assert sesion.get(Cuenta, "ana") is None


def test_registrar_confirma_la_transaccion(bd: sessionmaker[Session]):
    registrar_en(bd)
    with bd() as sesion:
        assert sesion.execute(text("SELECT count(*) FROM cuentas")).scalar() == 2
