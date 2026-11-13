"""Casos de uso cargar y transferir (SPEC 5.4 a 5.6)."""

from uuid import uuid4

import pytest

from app.domain.constantes import TOPE_OPERACION
from app.domain.errores import (
    ClaveReutilizada,
    ErrorDominio,
    MontoInvalido,
    NoAutenticado,
    NoEncontrado,
    SaldoInsuficiente,
    SobreElTope,
    TransferenciaASiMismo,
)
from app.services.libro import TransaccionRegistrada
from app.services.nucleo import cargar, transferir
from app.services.reintentos import reiniciar_contador, reintentos_por_codigo
from tests.db.sql_directo import crear_bolsa, insertar_participante
from tests.services.apoyo_libro import AHORA, contar, crear_usuario, saldo


@pytest.fixture(autouse=True)
def sin_reintentos():
    """Ninguna prueba del núcleo debe necesitar un reintento (SPEC 10.4)."""
    reiniciar_contador()
    yield
    assert reintentos_por_codigo() == {}


@pytest.fixture
def ana(bd) -> str:
    return crear_usuario(bd, "ana", "1000001")


@pytest.fixture
def beto(bd) -> str:
    return crear_usuario(bd, "beto", "1000002")


def hacer_cargar(bd, token, monto, clave=None):
    with bd() as sesion:
        return cargar(sesion, token, clave or uuid4(), monto, AHORA)


def hacer_transferir(bd, token, destino, monto, clave=None):
    with bd() as sesion:
        return transferir(sesion, token, clave or uuid4(), destino, monto, AHORA)


# --- Casos normales ---------------------------------------------------------


def test_cargar_crea_transaccion_dos_movimientos_y_saldos_exactos(bd, ana):
    respuesta = hacer_cargar(bd, ana, 100_000)
    assert respuesta == TransaccionRegistrada(
        id=respuesta.id,
        tipo="carga",
        origen="sistema",
        destino="ana",
        monto=100_000,
        creado_en=AHORA,
    )
    assert saldo(bd, "ana") == 100_000  # 0 + 100.000
    assert saldo(bd, "sistema") == -100_000  # 0 - 100.000
    assert contar(bd, "transacciones") == 1
    assert contar(bd, "movimientos") == 2
    assert contar(bd, "claves_idempotencia") == 1


def test_transferir_mueve_monto_exacto(bd, ana, beto):
    hacer_cargar(bd, ana, 100_000)
    respuesta = hacer_transferir(bd, ana, "beto", 30_000)
    assert respuesta == TransaccionRegistrada(
        id=respuesta.id,
        tipo="transferencia",
        origen="ana",
        destino="beto",
        monto=30_000,
        creado_en=AHORA,
    )
    assert saldo(bd, "ana") == 70_000  # 100.000 - 30.000
    assert saldo(bd, "beto") == 30_000  # 0 + 30.000
    assert saldo(bd, "sistema") == -100_000
    assert contar(bd, "transacciones") == 2
    assert contar(bd, "movimientos") == 4


def test_transferir_todo_el_saldo_deja_cero(bd, ana, beto):
    hacer_cargar(bd, ana, 50_000)
    hacer_transferir(bd, ana, "beto", 50_000)
    assert saldo(bd, "ana") == 0
    assert saldo(bd, "beto") == 50_000


def test_cargar_monto_igual_al_tope_se_acepta(bd, ana):
    hacer_cargar(bd, ana, TOPE_OPERACION)
    assert saldo(bd, "ana") == TOPE_OPERACION


def test_cargar_monto_uno_se_acepta(bd, ana):
    hacer_cargar(bd, ana, 1)
    assert saldo(bd, "ana") == 1


# --- Errores ---------------------------------------------------------------


def exigir_rechazo(bd, error: type[ErrorDominio], codigo: str, accion) -> None:
    """Exige la excepción y su código, y que no quede rastro en el libro."""
    transacciones = contar(bd, "transacciones")
    claves = contar(bd, "claves_idempotencia")
    with pytest.raises(error) as capturado:
        accion()
    assert capturado.value.codigo == codigo
    assert contar(bd, "transacciones") == transacciones
    assert contar(bd, "claves_idempotencia") == claves


@pytest.mark.parametrize(
    ("monto", "error", "codigo"),
    [
        (0, MontoInvalido, "monto_invalido"),
        (-1, MontoInvalido, "monto_invalido"),
        (TOPE_OPERACION + 1, SobreElTope, "sobre_el_tope"),
    ],
)
def test_cargar_monto_invalido_se_rechaza_sin_rastro(bd, ana, monto, error, codigo):
    exigir_rechazo(bd, error, codigo, lambda: hacer_cargar(bd, ana, monto))
    assert saldo(bd, "ana") == 0


@pytest.mark.parametrize(
    ("monto", "error", "codigo"),
    [
        (0, MontoInvalido, "monto_invalido"),
        (-1, MontoInvalido, "monto_invalido"),
        (TOPE_OPERACION + 1, SobreElTope, "sobre_el_tope"),
    ],
)
def test_transferir_monto_invalido_se_rechaza_sin_rastro(
    bd, ana, beto, monto, error, codigo
):
    hacer_cargar(bd, ana, 100_000)
    exigir_rechazo(bd, error, codigo, lambda: hacer_transferir(bd, ana, "beto", monto))
    assert saldo(bd, "ana") == 100_000
    assert saldo(bd, "beto") == 0


def test_transferir_a_si_mismo_se_rechaza(bd, ana):
    hacer_cargar(bd, ana, 100_000)
    exigir_rechazo(
        bd,
        TransferenciaASiMismo,
        "transferencia_a_si_mismo",
        lambda: hacer_transferir(bd, ana, "ana", 1_000),
    )
    assert saldo(bd, "ana") == 100_000


@pytest.mark.parametrize("destino", ["nadie", "sistema", "bolsa-ana-viaje"])
def test_transferir_a_destino_no_personal_da_no_encontrado(bd, ana, beto, destino):
    with bd() as sesion, sesion.begin():
        bolsa = crear_bolsa(sesion, "ana")
        insertar_participante(sesion, bolsa, "ana", 5000)
        insertar_participante(sesion, bolsa, "beto", 5000)
    hacer_cargar(bd, ana, 100_000)
    exigir_rechazo(
        bd,
        NoEncontrado,
        "no_encontrado",
        lambda: hacer_transferir(bd, ana, destino, 1_000),
    )
    assert saldo(bd, "ana") == 100_000
    assert saldo(bd, "sistema") == -100_000
    assert saldo(bd, "bolsa-ana-viaje") == 0


def test_transferir_con_saldo_insuficiente_se_rechaza(bd, ana, beto):
    hacer_cargar(bd, ana, 10_000)
    exigir_rechazo(
        bd,
        SaldoInsuficiente,
        "saldo_insuficiente",
        lambda: hacer_transferir(bd, ana, "beto", 10_001),
    )
    assert saldo(bd, "ana") == 10_000
    assert saldo(bd, "beto") == 0


@pytest.mark.parametrize("operacion", ["cargar", "transferir"])
def test_token_invalido_da_no_autenticado(bd, ana, beto, operacion):
    def accion():
        if operacion == "cargar":
            return hacer_cargar(bd, "token-falso", 1_000)
        return hacer_transferir(bd, "token-falso", "beto", 1_000)

    exigir_rechazo(bd, NoAutenticado, "no_autenticado", accion)


# --- Idempotencia ------------------------------------------------------------


def test_cargar_misma_clave_mismo_cuerpo_devuelve_misma_respuesta(bd, ana):
    clave = uuid4()
    primera = hacer_cargar(bd, ana, 100_000, clave)
    segunda = hacer_cargar(bd, ana, 100_000, clave)
    assert segunda == primera
    assert contar(bd, "transacciones") == 1
    assert contar(bd, "movimientos") == 2
    assert saldo(bd, "ana") == 100_000


def test_transferir_misma_clave_mismo_cuerpo_devuelve_misma_respuesta(bd, ana, beto):
    hacer_cargar(bd, ana, 100_000)
    clave = uuid4()
    primera = hacer_transferir(bd, ana, "beto", 30_000, clave)
    segunda = hacer_transferir(bd, ana, "beto", 30_000, clave)
    assert segunda == primera
    assert contar(bd, "transacciones") == 2
    assert saldo(bd, "ana") == 70_000
    assert saldo(bd, "beto") == 30_000


def test_misma_clave_otro_cuerpo_da_clave_reutilizada(bd, ana, beto):
    hacer_cargar(bd, ana, 100_000)
    clave = uuid4()
    hacer_transferir(bd, ana, "beto", 30_000, clave)
    exigir_rechazo(
        bd,
        ClaveReutilizada,
        "clave_reutilizada",
        lambda: hacer_transferir(bd, ana, "beto", 30_001, clave),
    )
    assert saldo(bd, "ana") == 70_000


def test_misma_clave_en_otra_operacion_da_clave_reutilizada(bd, ana, beto):
    clave = uuid4()
    hacer_cargar(bd, ana, 100_000, clave)
    exigir_rechazo(
        bd,
        ClaveReutilizada,
        "clave_reutilizada",
        lambda: hacer_transferir(bd, ana, "beto", 100_000, clave),
    )
    assert saldo(bd, "ana") == 100_000


def test_misma_clave_de_otro_usuario_es_independiente(bd, ana, beto):
    clave = uuid4()
    hacer_cargar(bd, ana, 1_000, clave)
    hacer_cargar(bd, beto, 1_000, clave)
    assert saldo(bd, "ana") == 1_000
    assert saldo(bd, "beto") == 1_000
    assert contar(bd, "claves_idempotencia") == 2


def test_reintento_tras_rechazo_se_ejecuta_como_nuevo(bd, ana, beto):
    clave = uuid4()
    with pytest.raises(SaldoInsuficiente):
        hacer_transferir(bd, ana, "beto", 30_000, clave)
    assert contar(bd, "claves_idempotencia") == 0
    hacer_cargar(bd, ana, 30_000)
    respuesta = hacer_transferir(bd, ana, "beto", 30_000, clave)
    assert respuesta.monto == 30_000
    assert saldo(bd, "ana") == 0
    assert saldo(bd, "beto") == 30_000


def test_clave_apunta_a_la_transaccion_creada(bd, ana):
    from sqlalchemy import text

    clave = uuid4()
    respuesta = hacer_cargar(bd, ana, 5_000, clave)
    with bd() as sesion:
        fila = sesion.execute(
            text(
                "SELECT operacion, transaccion_id, creado_en FROM claves_idempotencia "
                "WHERE cuenta_solicitante_id = 'ana' AND clave = :clave"
            ),
            {"clave": clave},
        ).one()
    assert fila.operacion == "cargar"
    assert fila.transaccion_id == respuesta.id
    assert fila.creado_en == AHORA
