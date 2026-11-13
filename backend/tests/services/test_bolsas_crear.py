"""Crear una bolsa (SPEC 6.2, T10)."""

from datetime import timedelta

import pytest
from sqlalchemy import text

from app.domain.errores import ErrorDominio
from app.services.bolsas import ConteoParticipantes, MiParticipacion
from tests.services.apoyo_bolsas import FECHA_LIMITE, conteos, crear
from tests.services.apoyo_libro import AHORA, crear_usuario


@pytest.fixture
def tokens(bd) -> dict[str, str]:
    nombres = ("ana", "beto", "carla", "olga")
    return {n: crear_usuario(bd, n, f"100000{i}") for i, n in enumerate(nombres)}


def verificar_codigo(excinfo, codigo: str) -> None:
    assert isinstance(excinfo.value, ErrorDominio)
    assert excinfo.value.codigo == codigo


def partes(bd, bolsa_id) -> dict[str, tuple[int, str]]:
    with bd() as sesion:
        filas = sesion.execute(
            text(
                "SELECT cuenta_id, parte, estado FROM participantes "
                "WHERE bolsa_id = :id"
            ),
            {"id": bolsa_id},
        ).all()
    return {f.cuenta_id: (f.parte, f.estado) for f in filas}


def test_bolsa_90000_entre_tres_da_partes_de_30000(bd, tokens):
    d = crear(bd, tokens["ana"])
    assert partes(bd, d.id) == {
        "ana": (30_000, "pendiente"),
        "beto": (30_000, "pendiente"),
        "carla": (30_000, "pendiente"),
    }
    assert d.nombre == "cena"
    assert d.creador == "ana"
    assert d.cuenta_objetivo == "olga"
    assert d.total == 90_000
    assert d.fecha_limite == FECHA_LIMITE
    assert d.transferir_al_vencer is True
    assert d.estado == "abierta"
    assert d.meta == 90_000
    assert d.aportado == 0
    assert d.transferido is None
    assert d.participantes == ConteoParticipantes(3, 3, 0, 0, 0)
    assert d.mi_participacion == MiParticipacion(30_000, "pendiente")
    with bd() as sesion:
        cuenta = sesion.execute(
            text("SELECT tipo, saldo FROM cuentas WHERE id = 'bolsa-ana-cena'")
        ).one()
    assert (cuenta.tipo, cuenta.saldo) == ("bolsa", 0)


def test_total_no_divisible_deja_el_sobrante_al_creador(bd, tokens):
    d = crear(bd, tokens["beto"], total=100_000)
    assert partes(bd, d.id) == {
        "ana": (33_333, "pendiente"),
        "beto": (33_334, "pendiente"),
        "carla": (33_333, "pendiente"),
    }
    assert d.mi_participacion.parte == 33_334
    assert d.meta == 100_000


def test_bolsa_creada_abierta_con_creada_en_igual_a_ahora(bd, tokens):
    d = crear(bd, tokens["ana"])
    with bd() as sesion:
        fila = sesion.execute(
            text("SELECT estado, creada_en, cuenta_id FROM bolsas WHERE id = :id"),
            {"id": d.id},
        ).one()
    assert fila.estado == "abierta"
    assert fila.creada_en == AHORA
    assert fila.cuenta_id == "bolsa-ana-cena"


def test_crear_no_mueve_dinero_ni_guarda_clave(bd, tokens):
    crear(bd, tokens["ana"])
    c = conteos(bd)
    assert c["transacciones"] == 0
    assert c["movimientos"] == 0
    assert c["claves_idempotencia"] == 0


def test_cuenta_objetivo_puede_ser_participante(bd, tokens):
    d = crear(bd, tokens["ana"], cuenta_objetivo="ana")
    assert d.cuenta_objetivo == "ana"


@pytest.mark.parametrize(
    ("participantes", "objetivo"),
    [
        pytest.param(("ana", "beto", "zoe"), "olga", id="participante_inexistente"),
        pytest.param(("ana", "beto"), "zoe", id="objetivo_inexistente"),
        pytest.param(("ana", "beto"), "sistema", id="objetivo_sistema"),
        pytest.param(("ana", "beto"), "bolsa-ana-previa", id="objetivo_de_bolsa"),
        pytest.param(("ana", "bolsa-ana-previa"), "olga", id="participante_de_bolsa"),
    ],
)
def test_cuenta_no_personal_da_no_encontrado(bd, tokens, participantes, objetivo):
    crear(bd, tokens["ana"], nombre="previa")
    antes = conteos(bd)
    with pytest.raises(ErrorDominio) as exc:
        crear(bd, tokens["ana"], participantes=participantes, cuenta_objetivo=objetivo)
    verificar_codigo(exc, "no_encontrado")
    assert conteos(bd) == antes


def test_nombre_repetido_del_mismo_creador_da_nombre_en_uso(bd, tokens):
    crear(bd, tokens["ana"])
    antes = conteos(bd)
    with pytest.raises(ErrorDominio) as exc:
        crear(bd, tokens["ana"], total=60_000, participantes=("ana", "beto"))
    verificar_codigo(exc, "nombre_en_uso")
    assert conteos(bd) == antes


def test_mismo_nombre_con_otro_creador_se_permite(bd, tokens):
    a = crear(bd, tokens["ana"])
    b = crear(bd, tokens["beto"])
    assert a.id != b.id
    assert b.creador == "beto"


@pytest.mark.parametrize(
    ("kwargs", "codigo"),
    [
        pytest.param(
            {"participantes": ("beto", "carla")},
            "participantes_invalidos",
            id="sin_creador",
        ),
        pytest.param(
            {"participantes": ("ana", "beto", "beto")},
            "participantes_invalidos",
            id="repetido",
        ),
        pytest.param({"total": 9_999}, "total_invalido", id="total_bajo"),
        pytest.param(
            {"fecha_limite": AHORA + timedelta(minutes=1)},
            "fecha_limite_invalida",
            id="fecha_cercana",
        ),
    ],
)
def test_error_de_dominio_no_deja_nada_escrito(bd, tokens, kwargs, codigo):
    antes = conteos(bd)
    with pytest.raises(ErrorDominio) as exc:
        crear(bd, tokens["ana"], **kwargs)
    verificar_codigo(exc, codigo)
    assert conteos(bd) == antes


def test_sin_sesion_da_no_autenticado(bd, tokens):
    antes = conteos(bd)
    with pytest.raises(ErrorDominio) as exc:
        crear(bd, "token-inexistente")
    verificar_codigo(exc, "no_autenticado")
    assert conteos(bd) == antes
