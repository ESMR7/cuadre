"""Aportar (SPEC 6.5, 6.8, 2.4, 2.5 y 10.3, T11)."""

from datetime import timedelta
from uuid import uuid4

import pytest

from app.services.libro import TransaccionRegistrada
from tests.services.apoyo_libro import AHORA, capturar_sql
from tests.services.apoyo_operaciones_bolsa import (
    FECHA_CORTA,
    SALDO_INICIAL,
    Tx,
    clave_guardada,
    esperar_error,
    estado_bolsa,
    estados,
    hacer_aportar,
    hacer_retirarse,
    nueva_bolsa,
    saldo_de,
    sin_reintentos,  # noqa: F401
    transacciones,
    usuarios,
)

pytestmark = pytest.mark.usefixtures("sin_reintentos")


@pytest.fixture
def tokens(bd):
    return usuarios(bd, "ana", "beto", "carla", "olga")


# --- Caso normal ---------------------------------------------------------


def test_aporte_mueve_la_parte_y_pasa_a_pagado(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    r = hacer_aportar(bd, tokens["beto"], bolsa)
    assert isinstance(r, TransaccionRegistrada)
    assert (r.tipo, r.origen, r.destino, r.monto) == (
        "aporte",
        "beto",
        "bolsa-ana-cena",
        30_000,
    )
    assert r.creado_en == AHORA
    assert saldo_de(bd, "beto") == SALDO_INICIAL - 30_000
    assert saldo_de(bd, "bolsa-ana-cena") == 30_000
    assert estados(bd, bolsa) == {
        "ana": "pendiente",
        "beto": "pagado",
        "carla": "pendiente",
    }
    assert estado_bolsa(bd, bolsa) == "abierta"
    assert transacciones(bd, "transferencia_final") == []


def test_ultimo_aporte_transfiere_90000_y_cierra_en_cero(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    hacer_aportar(bd, tokens["ana"], bolsa)
    hacer_aportar(bd, tokens["beto"], bolsa)
    r = hacer_aportar(bd, tokens["carla"], bolsa)
    assert r.tipo == "aporte"  # la respuesta es solo el aporte (9.4)
    assert transacciones(bd, "transferencia_final") == [
        Tx("transferencia_final", "bolsa-ana-cena", "olga", 90_000)
    ]
    assert saldo_de(bd, "bolsa-ana-cena") == 0
    assert saldo_de(bd, "olga") == SALDO_INICIAL + 90_000
    assert estado_bolsa(bd, bolsa) == "cerrada"
    assert set(estados(bd, bolsa).values()) == {"pagado"}


def test_aporte_del_creador_incluye_el_sobrante(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens, total=100_000)
    assert hacer_aportar(bd, tokens["ana"], bolsa).monto == 33_334
    assert hacer_aportar(bd, tokens["beto"], bolsa).monto == 33_333
    hacer_aportar(bd, tokens["carla"], bolsa)
    assert transacciones(bd, "transferencia_final")[0].monto == 100_000


def test_aporte_completo_con_objetivo_igual_a_quien_paga(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens, cuenta_objetivo="carla")
    hacer_aportar(bd, tokens["ana"], bolsa)
    hacer_aportar(bd, tokens["beto"], bolsa)
    hacer_aportar(bd, tokens["carla"], bolsa)
    assert saldo_de(bd, "carla") == SALDO_INICIAL - 30_000 + 90_000
    assert estado_bolsa(bd, bolsa) == "cerrada"


# --- Orden de bloqueo y relectura del saldo ------------------------------


def _bloqueos(sentencias):
    """[(tabla, modo, sentencia, params)] de cada SELECT con bloqueo."""
    salida = []
    for sql, params in sentencias:
        plano = " ".join(sql.split())
        if "FOR NO KEY UPDATE" in plano:
            salida.append(("cuentas", "FOR NO KEY UPDATE", plano, params))
        elif "FOR UPDATE" in plano:
            tabla = "bolsas" if "FROM bolsas" in plano else "otra"
            salida.append((tabla, "FOR UPDATE", plano, params))
    return salida


def _cuenta_de(params) -> str:
    valores = params.values() if isinstance(params, dict) else params
    return next(
        v for v in valores if isinstance(v, str) and v != "personal" and v != "bolsa"
    )


def test_orden_de_sentencias_y_bloqueos(bd, tokens, motor_prueba):
    bolsa = nueva_bolsa(bd, tokens, cuenta_objetivo="beto")
    hacer_aportar(bd, tokens["ana"], bolsa)
    hacer_aportar(bd, tokens["carla"], bolsa)
    with capturar_sql(motor_prueba) as sentencias:
        hacer_aportar(bd, tokens["beto"], bolsa)  # completa la bolsa
    planas = [" ".join(s.split()) for s, _ in sentencias]
    i_clave = next(
        i
        for i, s in enumerate(planas)
        if s.startswith("INSERT INTO claves_idempotencia")
    )
    bloqueos = _bloqueos(sentencias)
    i_bloqueos = [planas.index(b[2]) for b in bloqueos]
    assert i_clave < i_bloqueos[0]
    assert bloqueos[0][:2] == ("bolsas", "FOR UPDATE")
    assert "FOR NO KEY UPDATE" not in bloqueos[0][2]
    cuentas = [b for b in bloqueos[1:]]
    assert all(b[:2] == ("cuentas", "FOR NO KEY UPDATE") for b in cuentas)
    # Una sentencia por cuenta, ascendente y sin repetidos: beto paga y es
    # el objetivo, así que aparece una sola vez.
    assert [_cuenta_de(b[3]) for b in cuentas] == ["beto", "bolsa-ana-cena"]


def test_aporte_que_no_completa_no_bloquea_la_cuenta_objetivo(bd, tokens, motor_prueba):
    bolsa = nueva_bolsa(bd, tokens)
    with capturar_sql(motor_prueba) as sentencias:
        hacer_aportar(bd, tokens["beto"], bolsa)
    cuentas = [_cuenta_de(b[3]) for b in _bloqueos(sentencias) if b[0] == "cuentas"]
    assert cuentas == ["beto", "bolsa-ana-cena"]


def test_saldo_de_la_bolsa_se_relee_con_sql_tras_cada_update(bd, tokens, motor_prueba):
    """_transferencia_final y _cerrar_en_cero leen el saldo con una sentencia
    nueva, nunca del objeto Cuenta en memoria.
    """
    bolsa = nueva_bolsa(bd, tokens)
    hacer_aportar(bd, tokens["ana"], bolsa)
    hacer_aportar(bd, tokens["beto"], bolsa)
    with capturar_sql(motor_prueba) as sentencias:
        hacer_aportar(bd, tokens["carla"], bolsa)
    planas = [(" ".join(s.split()), p) for s, p in sentencias]

    def lee_saldo_bolsa(sql, params):
        valores = params.values() if isinstance(params, dict) else params
        return (
            sql.startswith("SELECT")
            and "saldo" in sql
            and "cuentas" in sql
            and "FOR" not in sql
            and "bolsa-ana-cena" in list(valores)
        )

    updates = [i for i, (s, _) in enumerate(planas) if s.startswith("UPDATE cuentas")]
    i_final = next(
        i
        for i, (s, p) in enumerate(planas)
        if s.startswith("INSERT INTO transacciones") and "transferencia_final" in str(p)
    )
    # Antes de la transferencia final: lectura tras el UPDATE del aporte.
    updates_aporte = [i for i in updates if i < i_final]
    assert any(
        lee_saldo_bolsa(*planas[i]) for i in range(updates_aporte[-1] + 1, i_final)
    )
    # Antes de cerrar: lectura tras el último UPDATE de saldo.
    i_cierre = next(
        i for i, (s, _) in enumerate(planas) if s.startswith("UPDATE bolsas")
    )
    assert any(lee_saldo_bolsa(*planas[i]) for i in range(updates[-1] + 1, i_cierre))


# --- Errores -------------------------------------------------------------


def test_saldo_insuficiente(bd):
    tokens = usuarios(bd, "ana", "beto", "carla", "olga", saldo=0)
    bolsa = nueva_bolsa(bd, tokens)
    esperar_error(
        bd,
        "saldo_insuficiente",
        lambda: hacer_aportar(bd, tokens["beto"], bolsa),
        bolsa,
    )


def test_ya_pagado_da_estado_invalido(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    hacer_aportar(bd, tokens["beto"], bolsa)
    esperar_error(
        bd, "estado_invalido", lambda: hacer_aportar(bd, tokens["beto"], bolsa), bolsa
    )


def test_retirado_da_estado_invalido(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    hacer_retirarse(bd, tokens["beto"], bolsa)
    esperar_error(
        bd, "estado_invalido", lambda: hacer_aportar(bd, tokens["beto"], bolsa), bolsa
    )


def test_bolsa_cerrada_da_estado_invalido(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens, participantes=("ana", "beto"), total=60_000)
    hacer_retirarse(bd, tokens["beto"], bolsa)
    hacer_retirarse(bd, tokens["ana"], bolsa)  # cerrada sin dinero
    esperar_error(
        bd, "estado_invalido", lambda: hacer_aportar(bd, tokens["ana"], bolsa), bolsa
    )


def test_bolsa_cerrada_y_vencida_da_estado_invalido(bd, tokens):
    """El estado se revisa antes que el plazo (SPEC 8.2)."""
    bolsa = nueva_bolsa(bd, tokens, participantes=("ana", "beto"), total=60_000)
    hacer_retirarse(bd, tokens["beto"], bolsa)
    hacer_retirarse(bd, tokens["ana"], bolsa)
    esperar_error(
        bd,
        "estado_invalido",
        lambda: hacer_aportar(bd, tokens["ana"], bolsa, ahora=FECHA_CORTA),
        bolsa,
    )


def test_fuera_de_plazo_en_la_fecha_limite(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    esperar_error(
        bd,
        "fuera_de_plazo",
        lambda: hacer_aportar(bd, tokens["beto"], bolsa, ahora=FECHA_CORTA),
        bolsa,
    )


def test_un_instante_antes_de_la_fecha_limite_se_acepta(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    antes = FECHA_CORTA - timedelta(microseconds=1)
    assert hacer_aportar(bd, tokens["beto"], bolsa, ahora=antes).monto == 30_000


def test_no_participante_da_sin_permiso(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    esperar_error(
        bd, "sin_permiso", lambda: hacer_aportar(bd, tokens["olga"], bolsa), bolsa
    )


def test_no_participante_en_bolsa_cerrada_da_sin_permiso(bd, tokens):
    """La pertenencia se revisa antes que el estado."""
    bolsa = nueva_bolsa(bd, tokens, participantes=("ana", "beto"), total=60_000)
    hacer_retirarse(bd, tokens["beto"], bolsa)
    hacer_retirarse(bd, tokens["ana"], bolsa)
    esperar_error(
        bd, "sin_permiso", lambda: hacer_aportar(bd, tokens["olga"], bolsa), bolsa
    )


def test_bolsa_inexistente_da_no_encontrado(bd, tokens):
    esperar_error(
        bd, "no_encontrado", lambda: hacer_aportar(bd, tokens["ana"], uuid4())
    )


def test_sin_sesion_da_no_autenticado(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    esperar_error(
        bd,
        "no_autenticado",
        lambda: hacer_aportar(bd, "token-inexistente", bolsa),
        bolsa,
    )


# --- Idempotencia --------------------------------------------------------


def test_misma_clave_devuelve_el_aporte_original_sin_mover_dinero(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    clave = uuid4()
    original = hacer_aportar(bd, tokens["beto"], bolsa, clave)
    repetido = hacer_aportar(bd, tokens["beto"], bolsa, clave)
    assert repetido == original
    assert len(transacciones(bd, "aporte")) == 1
    assert saldo_de(bd, "beto") == SALDO_INICIAL - 30_000
    assert clave_guardada(bd, "beto", clave) == ("aportar", original.id)


def test_misma_clave_en_otra_bolsa_da_clave_reutilizada(bd, tokens):
    una = nueva_bolsa(bd, tokens, nombre="una")
    otra = nueva_bolsa(bd, tokens, nombre="otra")
    clave = uuid4()
    hacer_aportar(bd, tokens["beto"], una, clave)
    esperar_error(
        bd,
        "clave_reutilizada",
        lambda: hacer_aportar(bd, tokens["beto"], otra, clave),
        otra,
    )


def test_reintento_tras_un_cambio_de_estado_devuelve_el_original(bd, tokens):
    """SPEC 10.3: aportar, retirarse y repetir el aporte con la misma clave."""
    bolsa = nueva_bolsa(bd, tokens)
    clave = uuid4()
    original = hacer_aportar(bd, tokens["beto"], bolsa, clave)
    hacer_retirarse(bd, tokens["beto"], bolsa)
    antes = len(transacciones(bd))
    assert hacer_aportar(bd, tokens["beto"], bolsa, clave) == original
    assert len(transacciones(bd)) == antes
    assert estados(bd, bolsa)["beto"] == "retirado"
    assert saldo_de(bd, "beto") == SALDO_INICIAL


def test_misma_clave_tras_cerrar_devuelve_el_original(bd, tokens):
    bolsa = nueva_bolsa(bd, tokens)
    hacer_aportar(bd, tokens["ana"], bolsa)
    hacer_aportar(bd, tokens["beto"], bolsa)
    clave = uuid4()
    original = hacer_aportar(bd, tokens["carla"], bolsa, clave)
    assert hacer_aportar(bd, tokens["carla"], bolsa, clave) == original
    assert len(transacciones(bd, "transferencia_final")) == 1


# --- Última defensa: cierre en cero --------------------------------------


def test_cierre_con_saldo_distinto_de_cero_revierte(bd, tokens, monkeypatch):
    """La transferencia final mueve saldo − 1 (sus patas cuadran entre sí):
    `_cerrar_en_cero` encuentra $1 en la bolsa y revierte todo (SPEC 6.1).
    """
    import app.services.operaciones_bolsa as operaciones
    from app.services.operaciones_bolsa import BolsaInconsistente
    from tests.services.apoyo_bolsas import conteos

    bolsa = nueva_bolsa(bd, tokens)
    hacer_aportar(bd, tokens["ana"], bolsa)
    hacer_aportar(bd, tokens["beto"], bolsa)
    real = operaciones.registrar_transaccion

    def registrar_de_menos(sesion, tipo, origen, destino, monto, ahora):
        if tipo == "transferencia_final":
            monto -= 1
        return real(sesion, tipo, origen, destino, monto, ahora)

    monkeypatch.setattr(operaciones, "registrar_transaccion", registrar_de_menos)
    antes = conteos(bd)
    estados_antes = estados(bd, bolsa)
    clave = uuid4()
    with pytest.raises(BolsaInconsistente) as exc:
        hacer_aportar(bd, tokens["carla"], bolsa, clave)
    assert exc.traceback[-1].name == "_cerrar_en_cero"
    assert conteos(bd) == antes
    assert estados(bd, bolsa) == estados_antes
    assert estado_bolsa(bd, bolsa) == "abierta"
    assert clave_guardada(bd, "carla", clave) is None
    assert saldo_de(bd, "bolsa-ana-cena") == 60_000
