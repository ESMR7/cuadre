"""Rutas de bolsas (SPEC 9.2 y 9.4)."""

from uuid import uuid4

import pytest

from app.main import app
from tests.api.conftest import cargar, con_clave, entrar, error, registrar

FECHA = "2026-11-14T15:00:00Z"
NO_EXISTE = "00000000-0000-4000-8000-000000000000"
RUTAS_CON_ID = [
    ("get", "/bolsas/{id}"),
    ("get", "/bolsas/{id}/movimientos"),
    ("post", "/bolsas/{id}/aportes"),
    ("post", "/bolsas/{id}/retiro"),
    ("post", "/bolsas/{id}/confirmacion"),
    ("post", "/bolsas/{id}/cancelacion"),
]
LLAVES_DETALLE = {
    "id",
    "nombre",
    "creador",
    "cuenta_objetivo",
    "total",
    "fecha_limite",
    "transferir_al_vencer",
    "estado",
    "meta",
    "aportado",
    "transferido",
    "participantes",
    "mi_participacion",
}


@pytest.fixture
def carla(cliente):
    registrar(cliente, "carla", "1000003")
    return entrar(cliente, "carla")


@pytest.fixture
def dani(cliente):
    registrar(cliente, "dani", "1000004")
    return entrar(cliente, "dani")


def cuerpo_bolsa(**cambios):
    cuerpo = {
        "nombre": "cena_cumple",
        "total": 100000,
        "participantes": ["ana", "beto", "carla"],
        "cuenta_objetivo": "ana",
        "fecha_limite": FECHA,
        "transferir_al_vencer": True,
    }
    return {**cuerpo, **cambios}


def crear(cliente, cab, **cambios) -> dict:
    r = cliente.post("/bolsas", json=cuerpo_bolsa(**cambios), headers=cab)
    assert r.status_code == 201, r.text
    return r.json()


def pedir(cliente, metodo, ruta, cab, **kw):
    return getattr(cliente, metodo)(ruta, headers=cab, **kw)


def aportar(cliente, cab, bolsa_id, clave=None):
    return cliente.post(f"/bolsas/{bolsa_id}/aportes", headers=con_clave(cab, clave))


def detalle(cliente, cab, bolsa_id) -> dict:
    r = cliente.get(f"/bolsas/{bolsa_id}", headers=cab)
    assert r.status_code == 200, r.text
    return r.json()


def saldo(cliente, cab) -> int:
    return cliente.get("/cuenta", headers=cab).json()["saldo"]


# --- Crear -------------------------------------------------------------------


def test_crear_devuelve_201_igual_al_detalle(cliente, ana, beto, carla):
    creada = crear(cliente, ana)
    assert creada == detalle(cliente, ana, creada["id"])
    assert set(creada) == LLAVES_DETALLE
    sin_id = {k: v for k, v in creada.items() if k != "id"}
    assert sin_id == {
        "nombre": "cena_cumple",
        "creador": "ana",
        "cuenta_objetivo": "ana",
        "total": 100000,
        "fecha_limite": FECHA,
        "transferir_al_vencer": True,
        "estado": "abierta",
        "meta": 100000,
        "aportado": 0,
        "transferido": None,
        "participantes": {
            "total": 3,
            "pendientes": 3,
            "pagados": 0,
            "por_confirmar": 0,
            "retirados": 0,
        },
        "mi_participacion": {"parte": 33334, "estado": "pendiente"},
    }


def test_crear_normaliza_nombres_a_minusculas(cliente, ana, beto, carla):
    creada = crear(
        cliente,
        ana,
        nombre="Cena",
        participantes=["ANA", "Beto", "carla"],
        cuenta_objetivo="Ana",
    )
    assert creada["nombre"] == "cena"
    assert creada["cuenta_objetivo"] == "ana"
    cargar(cliente, beto, 50000)
    r = aportar(cliente, beto, creada["id"])
    assert r.status_code == 201, r.text
    assert r.json()["destino"] == "bolsa-ana-cena"


@pytest.mark.parametrize("nombre", ["", "a" * 41, "a-b", "ñandu", "con espacio"])
def test_nombre_bolsa_fuera_de_patron_da_forma_invalida(
    cliente, ana, beto, carla, nombre
):
    r = cliente.post("/bolsas", json=cuerpo_bolsa(nombre=nombre), headers=ana)
    assert error(r, 422, "forma_invalida")["campos"] == ["nombre"]


def test_crear_campo_desconocido_da_forma_invalida(cliente, ana, beto, carla):
    r = cliente.post("/bolsas", json=cuerpo_bolsa(extra=1), headers=ana)
    error(r, 422, "forma_invalida")


@pytest.mark.parametrize("campo", ["total", "transferir_al_vencer", "participantes"])
def test_crear_falta_campo_da_forma_invalida(cliente, ana, campo):
    cuerpo = cuerpo_bolsa()
    del cuerpo[campo]
    r = cliente.post("/bolsas", json=cuerpo, headers=ana)
    assert error(r, 422, "forma_invalida")["campos"] == [campo]


@pytest.mark.parametrize("total", ["100000", 100000.0, True])
def test_crear_total_no_entero_da_forma_invalida(cliente, ana, total):
    r = cliente.post("/bolsas", json=cuerpo_bolsa(total=total), headers=ana)
    assert error(r, 422, "forma_invalida")["campos"] == ["total"]


@pytest.mark.parametrize(
    "fecha",
    ["2026-12-01", "2026-12-01T10:00:00", "mañana", "", 1764583200],
)
def test_fecha_limite_sin_zona_o_invalida_da_forma_invalida(
    cliente, ana, beto, carla, fecha
):
    r = cliente.post("/bolsas", json=cuerpo_bolsa(fecha_limite=fecha), headers=ana)
    cuerpo = error(r, 422, "forma_invalida")
    assert cuerpo["campos"] == ["fecha_limite"]
    if isinstance(fecha, str) and fecha:
        assert fecha not in r.text.replace('"campos"', "")


@pytest.mark.parametrize(
    ("fecha", "esperada"),
    [
        ("2026-12-01T10:00:00Z", "2026-12-01T10:00:00Z"),
        ("2026-12-01T05:00:00-05:00", "2026-12-01T10:00:00Z"),
    ],
)
def test_fecha_limite_con_zona_se_acepta_y_sale_en_utc(
    cliente, ana, beto, carla, fecha, esperada
):
    assert crear(cliente, ana, fecha_limite=fecha)["fecha_limite"] == esperada


def test_crear_sin_token_da_401(cliente):
    error(cliente.post("/bolsas", json=cuerpo_bolsa()), 401, "no_autenticado")


@pytest.mark.parametrize(
    ("cambios", "http", "codigo"),
    [
        ({"total": 9999}, 422, "total_invalido"),
        ({"participantes": ["beto", "carla"]}, 422, "participantes_invalidos"),
        ({"fecha_limite": "2026-11-13T15:01:00Z"}, 422, "fecha_limite_invalida"),
        ({"participantes": ["ana", "nadie"]}, 404, "no_encontrado"),
        ({"cuenta_objetivo": "nadie"}, 404, "no_encontrado"),
    ],
)
def test_crear_errores_de_dominio_pasan_por_la_api(
    cliente, ana, beto, carla, cambios, http, codigo
):
    r = cliente.post("/bolsas", json=cuerpo_bolsa(**cambios), headers=ana)
    error(r, http, codigo)


def test_crear_nombre_repetido_da_nombre_en_uso(cliente, ana, beto, carla):
    crear(cliente, ana)
    r = cliente.post("/bolsas", json=cuerpo_bolsa(nombre="CENA_CUMPLE"), headers=ana)
    error(r, 409, "nombre_en_uso")


# --- Flujo completo ----------------------------------------------------------


def test_flujo_completo_tres_aportes_transfiere_y_cierra(cliente, ana, beto, carla):
    bolsa = crear(cliente, ana)["id"]
    for cab in (ana, beto, carla):
        cargar(cliente, cab, 50000)
    r = aportar(cliente, beto, bolsa)
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert isinstance(cuerpo["id"], int)
    del cuerpo["id"]
    assert cuerpo == {
        "tipo": "aporte",
        "origen": "beto",
        "destino": "bolsa-ana-cena_cumple",
        "monto": 33333,
        "creado_en": "2026-11-13T15:00:00Z",
    }
    assert aportar(cliente, carla, bolsa).status_code == 201
    intermedio = detalle(cliente, ana, bolsa)
    assert intermedio["aportado"] == 66666
    assert intermedio["participantes"]["pagados"] == 2
    assert aportar(cliente, ana, bolsa).status_code == 201

    final = detalle(cliente, beto, bolsa)
    assert final["estado"] == "cerrada"
    assert final["transferido"] == 100000
    assert final["aportado"] == 0
    assert final["participantes"]["pagados"] == 3
    assert final["mi_participacion"] == {"parte": 33333, "estado": "pagado"}
    assert saldo(cliente, ana) == 50000 - 33334 + 100000
    assert saldo(cliente, beto) == 50000 - 33333


def test_mis_movimientos_con_la_bolsa(cliente, ana, beto, carla):
    bolsa = crear(cliente, ana)["id"]
    cargar(cliente, beto, 50000)
    aportar(cliente, beto, bolsa)
    cliente.post(f"/bolsas/{bolsa}/retiro", headers=con_clave(beto))
    r = cliente.get(f"/bolsas/{bolsa}/movimientos", headers=beto)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["desde"] == 0 and cuerpo["cantidad"] == 20
    assert sorted(
        (m["tipo"], m["contrapartida"], m["monto"]) for m in cuerpo["movimientos"]
    ) == [
        ("aporte", "bolsa-ana-cena_cumple", -33333),
        ("devolucion", "bolsa-ana-cena_cumple", 33333),
    ]
    assert set(cuerpo["movimientos"][0]) == {
        "tipo",
        "contrapartida",
        "monto",
        "creado_en",
    }


# --- Retiro, confirmación y cancelación --------------------------------------


def test_retiro_de_pagador_deja_a_los_demas_por_confirmar(cliente, ana, beto, carla):
    bolsa = crear(cliente, ana)["id"]
    for cab in (beto, carla):
        cargar(cliente, cab, 50000)
        assert aportar(cliente, cab, bolsa).status_code == 201
    r = cliente.post(f"/bolsas/{bolsa}/retiro", headers=con_clave(beto))
    assert r.status_code == 200, r.text
    devolucion = r.json()["devolucion"]
    del devolucion["id"]
    assert devolucion == {
        "tipo": "devolucion",
        "origen": "bolsa-ana-cena_cumple",
        "destino": "beto",
        "monto": 33333,
        "creado_en": "2026-11-13T15:00:00Z",
    }
    visto_por_carla = detalle(cliente, carla, bolsa)
    assert visto_por_carla["mi_participacion"]["estado"] == "por_confirmar"
    assert visto_por_carla["meta"] == 100000 - 33333
    assert visto_por_carla["participantes"]["retirados"] == 1
    assert detalle(cliente, beto, bolsa)["mi_participacion"]["estado"] == "retirado"
    assert saldo(cliente, beto) == 50000


def test_retiro_sin_pago_devuelve_devolucion_null(cliente, ana, beto, carla):
    bolsa = crear(cliente, ana)["id"]
    r = cliente.post(f"/bolsas/{bolsa}/retiro", headers=con_clave(beto))
    assert r.status_code == 200
    assert r.json() == {"devolucion": None}


def test_confirmacion_devuelve_estado(cliente, ana, beto, carla):
    bolsa = crear(cliente, ana)["id"]
    for cab in (beto, carla):
        cargar(cliente, cab, 50000)
        aportar(cliente, cab, bolsa)
    cliente.post(f"/bolsas/{bolsa}/retiro", headers=con_clave(beto))
    r = cliente.post(f"/bolsas/{bolsa}/confirmacion", headers=carla)
    assert r.status_code == 200, r.text
    assert r.json() == {"estado_bolsa": "abierta", "mi_estado": "pagado"}


def test_confirmacion_final_cierra_la_bolsa(cliente, ana, beto, carla):
    bolsa = crear(cliente, ana)["id"]
    for cab in (ana, beto, carla):
        cargar(cliente, cab, 50000)
    aportar(cliente, ana, bolsa)
    aportar(cliente, carla, bolsa)
    cliente.post(f"/bolsas/{bolsa}/retiro", headers=con_clave(beto))
    assert cliente.post(f"/bolsas/{bolsa}/confirmacion", headers=ana).json() == {
        "estado_bolsa": "abierta",
        "mi_estado": "pagado",
    }
    r = cliente.post(f"/bolsas/{bolsa}/confirmacion", headers=carla)
    assert r.json() == {"estado_bolsa": "cerrada", "mi_estado": "pagado"}
    assert detalle(cliente, ana, bolsa)["transferido"] == 33334 + 33333


def test_cancelacion_por_creador_200(cliente, ana, beto, carla):
    bolsa = crear(cliente, ana)["id"]
    r = cliente.post(f"/bolsas/{bolsa}/cancelacion", headers=ana)
    assert r.status_code == 200, r.text
    assert set(r.json()) == {"estado_bolsa"}
    assert r.json()["estado_bolsa"] == detalle(cliente, ana, bolsa)["estado"]


def test_cancelacion_por_no_creador_403(cliente, ana, beto, carla):
    bolsa = crear(cliente, ana)["id"]
    error(
        cliente.post(f"/bolsas/{bolsa}/cancelacion", headers=beto), 403, "sin_permiso"
    )


def test_operacion_sobre_bolsa_cerrada_da_estado_invalido(cliente, ana, beto, carla):
    bolsa = crear(cliente, ana)["id"]
    for cab in (ana, beto, carla):
        cargar(cliente, cab, 50000)
        aportar(cliente, cab, bolsa)
    error(aportar(cliente, beto, bolsa), 409, "estado_invalido")


def test_aporte_sin_saldo_da_saldo_insuficiente(cliente, ana, beto, carla):
    bolsa = crear(cliente, ana)["id"]
    error(aportar(cliente, beto, bolsa), 409, "saldo_insuficiente")


# --- Permisos, existencia y forma --------------------------------------------


@pytest.mark.parametrize(("metodo", "ruta"), RUTAS_CON_ID)
def test_no_participante_recibe_403(cliente, ana, beto, carla, dani, metodo, ruta):
    bolsa = crear(cliente, ana)["id"]
    r = pedir(cliente, metodo, ruta.format(id=bolsa), con_clave(dani))
    error(r, 403, "sin_permiso")


@pytest.mark.parametrize(("metodo", "ruta"), RUTAS_CON_ID)
def test_bolsa_inexistente_da_404(cliente, ana, metodo, ruta):
    r = pedir(cliente, metodo, ruta.format(id=NO_EXISTE), con_clave(ana))
    error(r, 404, "no_encontrado")


@pytest.mark.parametrize(("metodo", "ruta"), RUTAS_CON_ID)
@pytest.mark.parametrize("bolsa_id", ["123", "no-es-uuid"])
def test_id_no_uuid_da_forma_invalida(cliente, ana, metodo, ruta, bolsa_id):
    r = pedir(cliente, metodo, ruta.format(id=bolsa_id), con_clave(ana))
    error(r, 422, "forma_invalida")


@pytest.mark.parametrize(("metodo", "ruta"), RUTAS_CON_ID)
def test_sin_token_da_401_en_rutas_de_bolsas(cliente, metodo, ruta):
    r = pedir(
        cliente, metodo, ruta.format(id=NO_EXISTE), {"Idempotency-Key": str(uuid4())}
    )
    error(r, 401, "no_autenticado")


@pytest.mark.parametrize("operacion", ["aportes", "retiro"])
def test_aporte_y_retiro_sin_clave_dan_400(cliente, ana, beto, carla, operacion):
    bolsa = crear(cliente, ana)["id"]
    r = cliente.post(f"/bolsas/{bolsa}/{operacion}", headers=beto)
    error(r, 400, "falta_clave_idempotencia")


@pytest.mark.parametrize("operacion", ["aportes", "retiro"])
def test_clave_no_uuid_da_422(cliente, ana, beto, carla, operacion):
    bolsa = crear(cliente, ana)["id"]
    r = cliente.post(
        f"/bolsas/{bolsa}/{operacion}", headers={**beto, "Idempotency-Key": "abc"}
    )
    error(r, 422, "forma_invalida")


def test_confirmacion_y_cancelacion_no_exigen_clave(cliente, ana, beto, carla):
    bolsa = crear(cliente, ana)["id"]
    r = cliente.post(f"/bolsas/{bolsa}/confirmacion", headers=beto)
    error(r, 409, "estado_invalido")
    assert cliente.post(f"/bolsas/{bolsa}/cancelacion", headers=ana).status_code == 200


def test_cuerpo_enviado_se_ignora_en_operaciones_sin_cuerpo(cliente, ana, beto, carla):
    bolsa = crear(cliente, ana)["id"]
    cargar(cliente, beto, 50000)
    basura = '{"monto": 1, "x": ['

    def post(ruta, cab):
        return cliente.post(
            f"/bolsas/{bolsa}/{ruta}",
            content=basura,
            headers={**cab, "Content-Type": "application/json"},
        )

    cargar(cliente, carla, 50000)
    aportar(cliente, carla, bolsa)
    assert post("aportes", con_clave(beto)).status_code == 201
    assert post("retiro", con_clave(beto)).status_code == 200
    assert post("confirmacion", carla).status_code == 200
    assert post("cancelacion", ana).status_code == 200


# --- Idempotencia ------------------------------------------------------------


def test_reintento_aporte_misma_clave_devuelve_lo_mismo(cliente, ana, beto, carla):
    bolsa = crear(cliente, ana)["id"]
    cargar(cliente, beto, 50000)
    clave = str(uuid4())
    primera = aportar(cliente, beto, bolsa, clave)
    segunda = aportar(cliente, beto, bolsa, clave)
    assert primera.status_code == segunda.status_code == 201
    assert primera.json() == segunda.json()
    assert saldo(cliente, beto) == 50000 - 33333
    movs = cliente.get(f"/bolsas/{bolsa}/movimientos", headers=beto).json()
    assert len(movs["movimientos"]) == 1


def test_reintento_retiro_misma_clave_devuelve_lo_mismo(cliente, ana, beto, carla):
    bolsa = crear(cliente, ana)["id"]
    cargar(cliente, beto, 50000)
    aportar(cliente, beto, bolsa)
    clave = str(uuid4())
    ruta = f"/bolsas/{bolsa}/retiro"
    primera = cliente.post(ruta, headers=con_clave(beto, clave))
    segunda = cliente.post(ruta, headers=con_clave(beto, clave))
    assert primera.status_code == segunda.status_code == 200
    assert primera.json() == segunda.json()
    assert saldo(cliente, beto) == 50000


def test_misma_clave_en_otra_bolsa_da_clave_reutilizada(cliente, ana, beto, carla):
    b1 = crear(cliente, ana)["id"]
    b2 = crear(cliente, ana, nombre="otra")["id"]
    cargar(cliente, beto, 100000)
    clave = str(uuid4())
    assert aportar(cliente, beto, b1, clave).status_code == 201
    error(aportar(cliente, beto, b2, clave), 409, "clave_reutilizada")


# --- Privacidad y listado ----------------------------------------------------


def test_participante_no_ve_estado_de_otro(cliente, ana, beto, carla):
    bolsa = crear(cliente, ana)["id"]
    cargar(cliente, carla, 50000)
    aportar(cliente, carla, bolsa)
    visto = detalle(cliente, beto, bolsa)
    assert set(visto) == LLAVES_DETALLE
    assert visto["mi_participacion"] == {"parte": 33333, "estado": "pendiente"}
    assert set(visto["participantes"]) == {
        "total",
        "pendientes",
        "pagados",
        "por_confirmar",
        "retirados",
    }
    assert "carla" not in str(visto)
    movs = cliente.get(f"/bolsas/{bolsa}/movimientos", headers=beto).json()
    assert movs["movimientos"] == []


def test_mis_bolsas_ordenadas_y_paginadas(cliente, ana, beto, carla, reloj):
    from datetime import timedelta

    crear(cliente, ana, nombre="primera")
    reloj.ahora += timedelta(seconds=1)
    segunda = crear(cliente, beto, nombre="segunda", cuenta_objetivo="beto")
    r = cliente.get("/bolsas", headers=carla)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert [b["nombre"] for b in cuerpo["bolsas"]] == ["segunda", "primera"]
    assert cuerpo["desde"] == 0 and cuerpo["cantidad"] == 20
    assert cuerpo["bolsas"][0] == {
        "id": segunda["id"],
        "nombre": "segunda",
        "estado": "abierta",
        "fecha_limite": FECHA,
        "mi_parte": 33333,
        "mi_estado": "pendiente",
    }
    pagina = cliente.get("/bolsas?desde=1&cantidad=1", headers=carla).json()
    assert [b["nombre"] for b in pagina["bolsas"]] == ["primera"]
    assert (pagina["desde"], pagina["cantidad"]) == (1, 1)


@pytest.mark.parametrize("consulta", ["desde=-1", "cantidad=0", "cantidad=101"])
def test_paginacion_fuera_de_rango_da_422(cliente, ana, beto, carla, consulta):
    error(cliente.get(f"/bolsas?{consulta}", headers=ana), 422, "forma_invalida")
    bolsa = crear(cliente, ana)["id"]
    r = cliente.get(f"/bolsas/{bolsa}/movimientos?{consulta}", headers=ana)
    error(r, 422, "forma_invalida")


def test_ninguna_ruta_recibe_hora_ni_ejecuta_barrido():
    for ruta in app.routes:
        camino = getattr(ruta, "path", "")
        assert "barrido" not in camino and "vencidas" not in camino
        dependiente = getattr(ruta, "dependant", None)
        if dependiente is None:
            continue
        nombres = {
            p.name
            for p in (
                dependiente.query_params
                + dependiente.body_params
                + dependiente.header_params
                + dependiente.path_params
            )
        }
        assert "ahora" not in nombres
