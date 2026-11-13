"""Login, autenticación, renovación y logout (SPEC 1.4 y 5.3)."""

import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.modelos import Cuenta, Sesion, Usuario
from app.domain.constantes import DURACION_SESION
from app.domain.errores import NoAutenticado
from app.services.sesiones import (
    Autenticado,
    SesionIniciada,
    autenticar,
    cerrar_sesion,
    iniciar_sesion,
    renovar,
)
from app.services.usuarios import registrar

AHORA = datetime(2026, 11, 13, 15, 0, tzinfo=UTC)
CONTRASENA = "clave-segura-1"
UN_US = timedelta(microseconds=1)


@pytest.fixture
def ana(bd: sessionmaker[Session]) -> sessionmaker[Session]:
    with bd() as sesion:
        registrar(sesion, "ana", "1234567", CONTRASENA, AHORA)
    return bd


def login(bd, ahora=AHORA, nombre="ana", contrasena=CONTRASENA) -> SesionIniciada:
    with bd() as sesion:
        return iniciar_sesion(sesion, nombre, contrasena, ahora)


def autenticar_en(bd, token, ahora) -> Autenticado:
    with bd() as sesion, sesion.begin():
        return autenticar(sesion, token, ahora)


def test_duracion_sesion_es_20_minutos():
    assert DURACION_SESION == timedelta(minutes=20)


def test_login_correcto_devuelve_token_y_expira_en_20_min(ana):
    resultado = login(ana)
    assert isinstance(resultado.token, str) and len(resultado.token) >= 43
    assert resultado.expira_en == AHORA + timedelta(minutes=20)
    with ana() as sesion:
        fila = sesion.scalars(select(Sesion)).one()
        assert (fila.creada_en, fila.expira_en) == (AHORA, resultado.expira_en)


def test_login_guarda_solo_el_sha256_del_token(ana):
    resultado = login(ana)
    with ana() as sesion:
        guardado = sesion.scalar(select(Sesion.token_hash))
    assert guardado == hashlib.sha256(resultado.token.encode()).hexdigest()
    assert resultado.token not in guardado


def test_login_contrasena_incorrecta_da_no_autenticado(ana):
    with pytest.raises(NoAutenticado):
        login(ana, contrasena="otra-clave-9")
    with ana() as sesion:
        assert sesion.scalar(select(func.count()).select_from(Sesion)) == 0


def test_login_usuario_inexistente_da_el_mismo_error(ana):
    with pytest.raises(NoAutenticado) as incorrecta:
        login(ana, contrasena="otra-clave-9")
    with pytest.raises(NoAutenticado) as inexistente:
        login(ana, nombre="nadie")
    assert type(incorrecta.value) is type(inexistente.value)
    assert incorrecta.value.codigo == inexistente.value.codigo
    assert incorrecta.value.mensaje == inexistente.value.mensaje


def test_autenticar_token_vigente_devuelve_ids(ana):
    token = login(ana).token
    with ana() as sesion, sesion.begin():
        resultado = autenticar(sesion, token, AHORA)
        assert not any(isinstance(o, Cuenta) for o in sesion.identity_map.values())
    with ana() as sesion:
        usuario_id = sesion.scalar(select(Usuario.id))
    assert resultado == Autenticado(usuario_id=usuario_id, cuenta_id="ana")


def test_autenticar_justo_en_expira_en_falla(ana):
    resultado = login(ana)
    with pytest.raises(NoAutenticado):
        autenticar_en(ana, resultado.token, resultado.expira_en)


def test_autenticar_un_microsegundo_antes_funciona(ana):
    resultado = login(ana)
    autenticado = autenticar_en(ana, resultado.token, resultado.expira_en - UN_US)
    assert autenticado.cuenta_id == "ana"


def test_autenticar_token_inexistente_falla(ana):
    login(ana)
    with pytest.raises(NoAutenticado):
        autenticar_en(ana, "token-que-no-existe", AHORA)


def test_dos_logins_seguidos_solo_el_ultimo_es_valido(ana):
    primero = login(ana)
    segundo = login(ana, ahora=AHORA + timedelta(minutes=1))
    assert primero.token != segundo.token
    ahora = AHORA + timedelta(minutes=2)
    with pytest.raises(NoAutenticado):
        autenticar_en(ana, primero.token, ahora)
    assert autenticar_en(ana, segundo.token, ahora).cuenta_id == "ana"
    with ana() as sesion:
        usuario_id = sesion.scalar(select(Usuario.id))
        filas = sesion.scalar(
            select(func.count())
            .select_from(Sesion)
            .where(Sesion.usuario_id == usuario_id)
        )
    assert filas == 1


def test_renovar_vigente_mueve_expira_en(ana):
    resultado = login(ana)
    ahora = AHORA + timedelta(minutes=15)
    with ana() as sesion:
        nueva = renovar(sesion, resultado.token, ahora)
    assert nueva == ahora + timedelta(minutes=20)
    with ana() as sesion:
        assert sesion.scalar(select(Sesion.expira_en)) == nueva
    # El mismo token sigue valiendo después del plazo original.
    assert autenticar_en(ana, resultado.token, resultado.expira_en).cuenta_id == "ana"


@pytest.mark.parametrize("despues", [timedelta(0), timedelta(minutes=5)])
def test_renovar_token_vencido_falla(ana, despues):
    resultado = login(ana)
    with ana() as sesion, pytest.raises(NoAutenticado):
        renovar(sesion, resultado.token, resultado.expira_en + despues)
    with ana() as sesion:
        assert sesion.scalar(select(Sesion.expira_en)) == resultado.expira_en


def test_renovar_token_inexistente_falla(ana):
    with ana() as sesion, pytest.raises(NoAutenticado):
        renovar(sesion, "token-que-no-existe", AHORA)


def test_logout_borra_la_sesion_y_el_token_deja_de_valer(ana):
    resultado = login(ana)
    with ana() as sesion:
        assert cerrar_sesion(sesion, resultado.token, AHORA) is None
    with ana() as sesion:
        assert sesion.scalar(select(func.count()).select_from(Sesion)) == 0
    with pytest.raises(NoAutenticado):
        autenticar_en(ana, resultado.token, AHORA)


def test_logout_con_token_invalido_falla(ana):
    resultado = login(ana)
    with ana() as sesion, pytest.raises(NoAutenticado):
        cerrar_sesion(sesion, "token-que-no-existe", AHORA)
    with ana() as sesion, pytest.raises(NoAutenticado):
        cerrar_sesion(sesion, resultado.token, resultado.expira_en)
