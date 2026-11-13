"""Validación de creación de una bolsa (SPEC 1.5 y 6.2)."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.domain.bolsas import validar_creacion
from app.domain.errores import ErrorDominio

AHORA = datetime(2026, 11, 13, 15, 0, tzinfo=UTC)
FECHA_OK = AHORA + timedelta(days=1)
TRES = ["ana", "beto", "carla"]
BOGOTA = timezone(timedelta(hours=-5))


def verificar_codigo(excinfo: pytest.ExceptionInfo[BaseException], codigo: str) -> None:
    assert isinstance(excinfo.value, ErrorDominio)
    assert excinfo.value.codigo == codigo


def validar(participantes=TRES, total=90_000, fecha=FECHA_OK, creador="ana", **kw):
    validar_creacion(creador, participantes, total, fecha, AHORA, **kw)


def test_creacion_valida():
    validar()


@pytest.mark.parametrize(
    "participantes",
    [
        pytest.param(["beto", "carla"], id="sin_creador"),
        pytest.param(["ana", "beto", "beto"], id="repetido"),
        pytest.param(["ana", "ana"], id="creador_repetido"),
        pytest.param(["ana"], id="uno"),
        pytest.param([], id="vacia"),
        pytest.param([f"u{i}" for i in range(50)] + ["ana"], id="cincuenta_y_uno"),
    ],
)
def test_participantes_invalidos(participantes):
    with pytest.raises(ErrorDominio) as exc:
        validar(participantes=participantes)
    verificar_codigo(exc, "participantes_invalidos")


@pytest.mark.parametrize("n", [2, 50])
def test_participantes_en_los_bordes_validos(n):
    validar(participantes=["ana"] + [f"u{i}" for i in range(n - 1)])


@pytest.mark.parametrize(
    ("total", "valido"),
    [
        (9_999, False),
        (10_000, True),
        (3 * 49_990_000, True),
        (3 * 49_990_000 + 1, False),
        (0, False),
        (-90_000, False),
    ],
)
def test_bordes_del_total(total, valido):
    if valido:
        validar(total=total)
    else:
        with pytest.raises(ErrorDominio) as exc:
            validar(total=total)
        verificar_codigo(exc, "total_invalido")


UN_SEG = timedelta(seconds=1)
MIN2 = timedelta(minutes=2)
DIAS30 = timedelta(days=30)


@pytest.mark.parametrize(
    ("fecha", "valido"),
    [
        pytest.param(AHORA + MIN2 - UN_SEG, False, id="2min_menos_1s"),
        pytest.param(AHORA + MIN2, True, id="2min"),
        pytest.param(AHORA + DIAS30, True, id="30dias"),
        pytest.param(AHORA + DIAS30 + UN_SEG, False, id="30dias_mas_1s"),
        pytest.param(
            (AHORA + MIN2 - UN_SEG).astimezone(BOGOTA), False, id="bog_2min_menos_1s"
        ),
        pytest.param((AHORA + MIN2).astimezone(BOGOTA), True, id="bog_2min"),
        pytest.param((AHORA + DIAS30).astimezone(BOGOTA), True, id="bog_30dias"),
        pytest.param(
            (AHORA + DIAS30 + UN_SEG).astimezone(BOGOTA), False, id="bog_30dias_mas_1s"
        ),
        pytest.param(AHORA - timedelta(days=1), False, id="pasada"),
    ],
)
def test_bordes_de_la_fecha_limite(fecha, valido):
    if valido:
        validar(fecha=fecha)
    else:
        with pytest.raises(ErrorDominio) as exc:
            validar(fecha=fecha)
        verificar_codigo(exc, "fecha_limite_invalida")


def test_otra_zona_mismo_instante_mismo_resultado():
    borde = AHORA + MIN2
    en_bogota = borde.astimezone(BOGOTA)
    assert en_bogota.utcoffset() == timedelta(hours=-5)
    assert en_bogota == borde
    validar(fecha=borde)
    validar(fecha=en_bogota)


def test_limites_de_fecha_configurables():
    validar(
        fecha=AHORA + timedelta(minutes=1), anticipacion_minima=timedelta(minutes=1)
    )
    with pytest.raises(ErrorDominio) as exc:
        validar(fecha=AHORA + timedelta(days=2), anticipacion_maxima=timedelta(days=1))
    verificar_codigo(exc, "fecha_limite_invalida")


def test_fecha_sin_zona_rechazada():
    with pytest.raises(ErrorDominio) as exc:
        validar(fecha=datetime(2026, 11, 14, 15, 0))
    verificar_codigo(exc, "fecha_limite_invalida")


def test_participantes_se_revisan_antes_que_el_total():
    with pytest.raises(ErrorDominio) as exc:
        validar(participantes=["ana"], total=1)
    verificar_codigo(exc, "participantes_invalidos")
