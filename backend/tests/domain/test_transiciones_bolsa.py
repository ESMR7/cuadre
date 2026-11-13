"""Transiciones puras de bolsas y participantes (SPEC 6.4, 7.1, 7.2 y 8.2).

Cada caso parametrizado lleva en su `id` la fila del SPEC que cubre, copiada
de la tabla.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.bolsas import (
    EstadoBolsa,
    EstadoParticipante,
    ResultadoTransicion,
    aportar,
    calcular_meta,
    cancelar,
    cerrar_liquidacion,
    confirmar,
    preparar_liquidacion,
    retirarse,
    verificar_operable,
)
from app.domain.errores import ErrorDominio

FECHA = datetime(2026, 11, 20, 15, 0, tzinfo=UTC)
ANTES = FECHA - timedelta(seconds=1)
DESPUES = FECHA

AB, CA, LI, CE = (
    EstadoBolsa.ABIERTA,
    EstadoBolsa.CANCELADA,
    EstadoBolsa.LIQUIDANDO,
    EstadoBolsa.CERRADA,
)
PE, PA, PC, RE = (
    EstadoParticipante.PENDIENTE,
    EstadoParticipante.PAGADO,
    EstadoParticipante.POR_CONFIRMAR,
    EstadoParticipante.RETIRADO,
)
TRANSFERIR, DEVOLVER = True, False


def p(ana, beto, carla, dani=None):
    estados = {"ana": ana, "beto": beto, "carla": carla}
    if dani is not None:
        estados["dani"] = dani
    return estados


def ejecutar(
    evento: str,
    estado: EstadoBolsa,
    participantes,
    usuario: str | None = None,
    politica: bool = TRANSFERIR,
    saldo: int = 0,
    ahora: datetime = ANTES,
    hay_deudas: bool = False,
) -> ResultadoTransicion:
    if evento == "aportar":
        return aportar(estado, participantes, usuario, FECHA, ahora)
    if evento == "retirarse":
        return retirarse(estado, participantes, usuario, FECHA, ahora)
    if evento == "confirmar":
        return confirmar(estado, participantes, usuario, FECHA, ahora)
    if evento == "cancelar":
        return cancelar(estado, participantes, politica, saldo, FECHA, ahora)
    if evento == "preparar":
        return preparar_liquidacion(estado, participantes, politica, FECHA, ahora)
    if evento == "cerrar":
        return cerrar_liquidacion(estado, participantes, politica, hay_deudas)
    raise AssertionError(evento)


def verificar_codigo(excinfo: pytest.ExceptionInfo[BaseException], codigo: str) -> None:
    assert isinstance(excinfo.value, ErrorDominio)
    assert excinfo.value.codigo == codigo


# --- Transiciones de la bolsa (SPEC 6.4 y 7.1) -------------------------------
# (evento, kwargs, estado, participantes, bolsa esperada, participantes
#  esperados, completa, cierra)

FILAS_BOLSA = [
    pytest.param(
        "aportar",
        {"usuario": "carla"},
        AB,
        p(PA, PA, PE),
        CE,
        p(PA, PA, PA),
        True,
        True,
        id="6.4 | abierta | Aportar o confirmar | Todos los activos quedan en pagado | cerrada (aportar)",
    ),
    pytest.param(
        "confirmar",
        {"usuario": "beto"},
        AB,
        p(PA, PC, RE),
        CE,
        p(PA, PA, RE),
        True,
        True,
        id="6.4 | abierta | Aportar o confirmar | Todos los activos quedan en pagado | cerrada (confirmar)",
    ),
    pytest.param(
        "retirarse",
        {"usuario": "carla"},
        AB,
        p(RE, RE, PE),
        CE,
        p(RE, RE, RE),
        False,
        True,
        id="6.4 | abierta | Retirarse | Era el último activo | cerrada",
    ),
    pytest.param(
        "cancelar",
        {"politica": TRANSFERIR},
        AB,
        p(PA, PE, PC),
        CA,
        p(PC, RE, PC),
        False,
        False,
        id="6.4 | abierta | Cancelar con transferir | Queda algún participante que había pagado | cancelada",
    ),
    pytest.param(
        "cancelar",
        {"politica": TRANSFERIR},
        AB,
        p(PE, PE, RE),
        CE,
        p(RE, RE, RE),
        False,
        True,
        id="6.4 | abierta | Cancelar con transferir | Nadie había pagado | cerrada",
    ),
    pytest.param(
        "cancelar",
        {"politica": DEVOLVER, "saldo": 30_000},
        AB,
        p(PA, PE, RE),
        LI,
        p(RE, RE, RE),
        False,
        False,
        id="6.4 | abierta | Cancelar con devolver | Saldo de la bolsa mayor que 0 | liquidando",
    ),
    pytest.param(
        "cancelar",
        {"politica": DEVOLVER, "saldo": 0},
        AB,
        p(PE, PE, RE),
        CE,
        p(RE, RE, RE),
        False,
        True,
        id="6.4 | abierta | Cancelar con devolver | Saldo de la bolsa en 0 | cerrada",
    ),
    pytest.param(
        "preparar",
        {"ahora": DESPUES},
        AB,
        p(PA, PE, PC),
        LI,
        p(PA, RE, RE),
        False,
        False,
        id="6.4 | abierta | Barrido | ahora >= fecha_limite | liquidando",
    ),
    pytest.param(
        "confirmar",
        {"usuario": "beto"},
        CA,
        p(PA, PC, RE),
        CE,
        p(PA, PA, RE),
        True,
        True,
        id="6.4 | cancelada | Confirmar | Todos los activos quedan en pagado | cerrada",
    ),
    pytest.param(
        "retirarse",
        {"usuario": "beto"},
        CA,
        p(RE, PC, RE),
        CE,
        p(RE, RE, RE),
        False,
        True,
        id="6.4 | cancelada | Retirarse | Era el último activo | cerrada",
    ),
    pytest.param(
        "preparar",
        {"ahora": DESPUES},
        CA,
        p(PA, PC, RE),
        LI,
        p(PA, RE, RE),
        False,
        False,
        id="6.4 | cancelada | Barrido | ahora >= fecha_limite | liquidando",
    ),
    pytest.param(
        "cerrar",
        {"hay_deudas": False},
        LI,
        p(PA, RE, RE),
        CE,
        p(PA, RE, RE),
        True,
        True,
        id="6.4 | liquidando | Barrido | Sin deudas pendientes | cerrada (con pagados: transferencia final)",
    ),
    pytest.param(
        "cerrar",
        {"hay_deudas": False},
        LI,
        p(RE, RE, RE),
        CE,
        p(RE, RE, RE),
        False,
        True,
        id="6.4 | liquidando | Barrido | Sin deudas pendientes | cerrada (sin pagados: sin transferencia)",
    ),
    # SPEC 7.1, viñetas de cancelar.
    pytest.param(
        "cancelar",
        {"politica": DEVOLVER, "saldo": 60_000},
        AB,
        p(PA, PC, PE),
        LI,
        p(RE, RE, RE),
        False,
        False,
        id="7.1 | Con devolver: todos los participantes pasan a retirado; saldo > 0 → liquidando",
    ),
    pytest.param(
        "cancelar",
        {"politica": TRANSFERIR},
        AB,
        p(PE, PC, RE),
        CA,
        p(RE, PC, RE),
        False,
        False,
        id="7.1 | Con transferir: pendiente → retirado, por_confirmar sigue activo → cancelada",
    ),
]


@pytest.mark.parametrize(
    (
        "evento",
        "kwargs",
        "estado",
        "participantes",
        "bolsa",
        "esperados",
        "completa",
        "cierra",
    ),
    FILAS_BOLSA,
)
def test_transicion_de_bolsa(
    evento, kwargs, estado, participantes, bolsa, esperados, completa, cierra
):
    original = dict(participantes)
    r = ejecutar(evento, estado, participantes, **kwargs)
    assert r.estado_bolsa == bolsa
    assert r.participantes == esperados
    assert r.completa is completa
    assert r.cierra is cierra
    assert participantes == original  # no muta la entrada


def test_cerrar_con_deudas_pendientes_no_cierra():
    """7.4 paso 3: si queda un retirado con deuda, el siguiente ciclo retoma."""
    r = ejecutar("cerrar", LI, p(PA, RE, RE), hay_deudas=True)
    assert r.estado_bolsa == LI
    assert r.cierra is False
    assert r.completa is False


def test_cerrar_con_devolver_nunca_completa():
    r = ejecutar("cerrar", LI, p(RE, RE, RE), politica=DEVOLVER)
    assert r.estado_bolsa == CE
    assert r.completa is False


# --- Transiciones del participante (SPEC 6.4 y 7.2) ---------------------------
# Cuatro participantes para que la bolsa no se cierre ni se complete. Se
# verifica el estado de `dani`.

FILAS_PARTICIPANTE = [
    pytest.param(
        "aportar",
        {"usuario": "dani"},
        AB,
        PE,
        PA,
        id="6.4 | pendiente | Aportar | pagado",
    ),
    pytest.param(
        "retirarse",
        {"usuario": "dani"},
        AB,
        PE,
        RE,
        id="6.4 | pendiente | Retirarse | retirado",
    ),
    pytest.param(
        "cancelar",
        {"politica": TRANSFERIR},
        AB,
        PE,
        RE,
        id="6.4 | pendiente | cancelación (transferir) | retirado",
    ),
    pytest.param(
        "cancelar",
        {"politica": DEVOLVER, "saldo": 30_000},
        AB,
        PE,
        RE,
        id="6.4 | pendiente | cancelación (devolver) | retirado",
    ),
    pytest.param(
        "preparar",
        {"ahora": DESPUES},
        AB,
        PE,
        RE,
        id="6.4 | pendiente | liquidación | retirado",
    ),
    pytest.param(
        "retirarse",
        {"usuario": "carla"},
        AB,
        PA,
        PC,
        id="6.4 | pagado | Otro participante se retira | por_confirmar",
    ),
    pytest.param(
        "cancelar",
        {"politica": TRANSFERIR},
        AB,
        PA,
        PC,
        id="6.4 | pagado | Cancelación con transferir | por_confirmar",
    ),
    pytest.param(
        "retirarse",
        {"usuario": "dani"},
        AB,
        PA,
        RE,
        id="6.4 | pagado | Retirarse | retirado",
    ),
    pytest.param(
        "cancelar",
        {"politica": DEVOLVER, "saldo": 30_000},
        AB,
        PA,
        RE,
        id="6.4 | pagado | Cancelación con devolver | retirado",
    ),
    pytest.param(
        "preparar",
        {"ahora": DESPUES, "politica": DEVOLVER},
        AB,
        PA,
        RE,
        id="6.4 | pagado | liquidación con devolver | retirado",
    ),
    pytest.param(
        "preparar",
        {"ahora": DESPUES, "politica": TRANSFERIR},
        AB,
        PA,
        PA,
        id="7.2 | pagado | liquidación con transferir | sigue pagado",
    ),
    pytest.param(
        "confirmar",
        {"usuario": "dani"},
        AB,
        PC,
        PA,
        id="6.4 | por_confirmar | Confirmar | pagado",
    ),
    pytest.param(
        "retirarse",
        {"usuario": "dani"},
        AB,
        PC,
        RE,
        id="6.4 | por_confirmar | Retirarse | retirado",
    ),
    pytest.param(
        "preparar",
        {"ahora": DESPUES, "politica": TRANSFERIR},
        AB,
        PC,
        RE,
        id="6.4 | por_confirmar | Liquidación (transferir) | retirado",
    ),
    pytest.param(
        "preparar",
        {"ahora": DESPUES, "politica": DEVOLVER},
        AB,
        PC,
        RE,
        id="6.4 | por_confirmar | Liquidación (devolver) | retirado",
    ),
]


@pytest.mark.parametrize(
    ("evento", "kwargs", "estado", "desde", "hacia"), FILAS_PARTICIPANTE
)
def test_transicion_de_participante(evento, kwargs, estado, desde, hacia):
    # ana y beto pendientes: la bolsa no se completa; carla pendiente: puede retirarse.
    r = ejecutar(evento, estado, p(PE, PE, PE, desde), **kwargs)
    assert r.participantes["dani"] == hacia


# --- Reglas que deben verse en las funciones (6.6 y 6.4) ---------------------


def test_retiro_pasa_pagados_a_por_confirmar_y_nunca_completa():
    """beto (pendiente) se retira y los demás ya pagaron: no completa."""
    r = ejecutar("retirarse", AB, p(PA, PE, PA), usuario="beto")
    assert r.participantes == p(PC, RE, PC)
    assert r.completa is False
    assert r.cierra is False
    assert r.estado_bolsa == AB
    assert r.habia_pagado is False


def test_ultimo_activo_pagado_se_retira_cierra_con_dinero_por_devolver():
    r = ejecutar("retirarse", AB, p(RE, RE, PA), usuario="carla")
    assert r.estado_bolsa == CE
    assert r.cierra is True
    assert r.habia_pagado is True
    assert r.completa is False


@pytest.mark.parametrize("desde", [PA, PC])
def test_retiro_de_quien_pago_marca_habia_pagado(desde):
    r = ejecutar("retirarse", AB, p(desde, PE, PE), usuario="ana")
    assert r.habia_pagado is True


def test_aporte_que_no_completa_deja_la_bolsa_abierta():
    r = ejecutar("aportar", AB, p(PE, PE, PE), usuario="ana")
    assert r.estado_bolsa == AB
    assert r.completa is False
    assert r.cierra is False


def test_por_confirmar_cuenta_como_pendiente_para_completar():
    r = ejecutar("aportar", AB, p(PC, PA, PE), usuario="carla")
    assert r.completa is False
    assert r.estado_bolsa == AB


# --- Errores -----------------------------------------------------------------

ERRORES = [
    pytest.param(
        "aportar",
        CA,
        p(PE, PE, PE),
        {"usuario": "ana"},
        "estado_invalido",
        id="aportar en cancelada",
    ),
    pytest.param(
        "aportar",
        LI,
        p(PE, PE, PE),
        {"usuario": "ana"},
        "estado_invalido",
        id="aportar en liquidando",
    ),
    pytest.param(
        "aportar",
        CE,
        p(PE, PE, PE),
        {"usuario": "ana"},
        "estado_invalido",
        id="aportar en cerrada",
    ),
    pytest.param(
        "aportar",
        AB,
        p(PA, PE, PE),
        {"usuario": "ana"},
        "estado_invalido",
        id="aportar ya pagado",
    ),
    pytest.param(
        "aportar",
        AB,
        p(PC, PE, PE),
        {"usuario": "ana"},
        "estado_invalido",
        id="aportar por_confirmar",
    ),
    pytest.param(
        "aportar",
        AB,
        p(RE, PE, PE),
        {"usuario": "ana"},
        "estado_invalido",
        id="aportar retirado",
    ),
    pytest.param(
        "aportar",
        AB,
        p(PE, PE, PE),
        {"usuario": "ana", "ahora": DESPUES},
        "fuera_de_plazo",
        id="aportar vencida",
    ),
    pytest.param(
        "aportar",
        AB,
        p(PE, PE, PE),
        {"usuario": "zoe"},
        "sin_permiso",
        id="aportar usuario ausente",
    ),
    pytest.param(
        "retirarse",
        AB,
        p(RE, PE, PE),
        {"usuario": "ana"},
        "estado_invalido",
        id="retirarse ya retirado",
    ),
    pytest.param(
        "retirarse",
        LI,
        p(PE, PE, PE),
        {"usuario": "ana"},
        "estado_invalido",
        id="retirarse en liquidando",
    ),
    pytest.param(
        "retirarse",
        CE,
        p(PE, PE, PE),
        {"usuario": "ana"},
        "estado_invalido",
        id="retirarse en cerrada",
    ),
    pytest.param(
        "retirarse",
        CA,
        p(PC, RE, RE),
        {"usuario": "ana", "ahora": DESPUES},
        "fuera_de_plazo",
        id="retirarse cancelada vencida",
    ),
    pytest.param(
        "retirarse",
        AB,
        p(PE, PE, PE),
        {"usuario": "zoe"},
        "sin_permiso",
        id="retirarse usuario ausente",
    ),
    pytest.param(
        "confirmar",
        AB,
        p(PA, PE, PE),
        {"usuario": "ana"},
        "estado_invalido",
        id="confirmar repetido (ya pagado)",
    ),
    pytest.param(
        "confirmar",
        AB,
        p(PE, PE, PE),
        {"usuario": "ana"},
        "estado_invalido",
        id="confirmar pendiente",
    ),
    pytest.param(
        "confirmar",
        AB,
        p(RE, PE, PE),
        {"usuario": "ana"},
        "estado_invalido",
        id="confirmar retirado",
    ),
    pytest.param(
        "confirmar",
        LI,
        p(PC, PE, PE),
        {"usuario": "ana"},
        "estado_invalido",
        id="confirmar en liquidando",
    ),
    pytest.param(
        "confirmar",
        CA,
        p(PC, RE, RE),
        {"usuario": "ana", "ahora": DESPUES},
        "fuera_de_plazo",
        id="confirmar cancelada vencida",
    ),
    pytest.param(
        "confirmar",
        AB,
        p(PC, PE, PE),
        {"usuario": "zoe"},
        "sin_permiso",
        id="confirmar usuario ausente",
    ),
    pytest.param(
        "cancelar", CA, p(PC, RE, RE), {}, "estado_invalido", id="cancelar cancelada"
    ),
    pytest.param(
        "cancelar", LI, p(PE, PE, PE), {}, "estado_invalido", id="cancelar liquidando"
    ),
    pytest.param(
        "cancelar", CE, p(RE, RE, RE), {}, "estado_invalido", id="cancelar cerrada"
    ),
    pytest.param(
        "cancelar",
        AB,
        p(PE, PE, PE),
        {"ahora": DESPUES},
        "fuera_de_plazo",
        id="cancelar vencida",
    ),
    pytest.param(
        "preparar",
        AB,
        p(PE, PE, PE),
        {"ahora": ANTES},
        "estado_invalido",
        id="preparar antes de la fecha límite",
    ),
    pytest.param(
        "preparar",
        LI,
        p(PE, PE, PE),
        {"ahora": DESPUES},
        "estado_invalido",
        id="preparar liquidando",
    ),
    pytest.param(
        "preparar",
        CE,
        p(RE, RE, RE),
        {"ahora": DESPUES},
        "estado_invalido",
        id="preparar cerrada",
    ),
    pytest.param(
        "cerrar", AB, p(PA, PE, PE), {}, "estado_invalido", id="cerrar abierta"
    ),
    pytest.param(
        "cerrar", CE, p(RE, RE, RE), {}, "estado_invalido", id="cerrar cerrada"
    ),
]


@pytest.mark.parametrize(
    ("evento", "estado", "participantes", "kwargs", "codigo"), ERRORES
)
def test_errores_de_transicion(evento, estado, participantes, kwargs, codigo):
    with pytest.raises(ErrorDominio) as exc:
        ejecutar(evento, estado, participantes, **kwargs)
    verificar_codigo(exc, codigo)


# --- Orden estado-plazo (SPEC 8.2) -------------------------------------------


@pytest.mark.parametrize("estado", [LI, CE])
def test_estado_se_revisa_antes_que_el_plazo(estado):
    with pytest.raises(ErrorDominio) as exc:
        verificar_operable(estado, {AB, CA}, FECHA, DESPUES + timedelta(days=1))
    verificar_codigo(exc, "estado_invalido")


def test_vigente_solo_si_ahora_menor_que_fecha_limite():
    verificar_operable(AB, {AB}, FECHA, FECHA - timedelta(microseconds=1))
    with pytest.raises(ErrorDominio) as exc:
        verificar_operable(AB, {AB}, FECHA, FECHA)
    verificar_codigo(exc, "fuera_de_plazo")


# --- Meta (SPEC 6.1) ---------------------------------------------------------


def test_meta_suma_solo_activos():
    partes = {"ana": 30_001, "beto": 30_000, "carla": 30_000}
    assert calcular_meta(partes, p(PA, PC, PE)) == 90_001
    assert calcular_meta(partes, p(PA, RE, PC)) == 60_001
    assert calcular_meta(partes, p(RE, RE, RE)) == 0
