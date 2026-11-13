"""Formato y tabla de errores, 404, 405, 500, CORS y no filtración (SPEC 2.6 y 9.1)."""

import logging
import subprocess
import sys

import app.api.cuenta
import app.domain.errores as errores_dominio
from app.api.errores import HTTP_POR_CODIGO
from tests.api.conftest import CONTRASENA, error


def test_ruta_desconocida_da_404_no_encontrado(cliente):
    error(cliente.get("/no-existe"), 404, "no_encontrado")


def test_metodo_no_permitido_da_405(cliente):
    r = cliente.put("/cargas", json={})
    error(r, 405, "metodo_no_permitido")
    assert "POST" in r.headers["allow"]


def test_json_mal_formado_da_forma_invalida(cliente):
    r = cliente.post(
        "/usuarios", content="{no es json", headers={"Content-Type": "application/json"}
    )
    error(r, 422, "forma_invalida")


def test_error_inesperado_da_500_sin_detalle(cliente, monkeypatch, caplog):
    def falla(*args, **kwargs):
        raise RuntimeError("postgresql://usuario:secreto@db/cuadre")

    monkeypatch.setattr(app.api.cuenta, "consultar_saldo", falla)
    with caplog.at_level(logging.DEBUG):
        r = cliente.get("/cuenta", headers={"Authorization": "Bearer x"})
    error(r, 500, "error_interno")
    assert "secreto" not in r.text and "postgresql" not in r.text
    assert "secreto" not in caplog.text and "postgresql" not in caplog.text
    assert "RuntimeError" in caplog.text


def test_tabla_de_codigos_cubre_todos_los_errores_de_dominio():
    clases = [
        c
        for c in vars(errores_dominio).values()
        if isinstance(c, type)
        and issubclass(c, errores_dominio.ErrorDominio)
        and c is not errores_dominio.ErrorDominio
    ]
    assert {c.codigo for c in clases} | {"error_interno"} == set(HTTP_POR_CODIGO)
    assert HTTP_POR_CODIGO["error_interno"] == 500


def test_errores_no_filtran_datos_sensibles(cliente, ana):
    cedula, token = "1000001", ana["Authorization"].split(" ")[1]
    respuestas = [
        # Registro repetido: no revela la cédula.
        cliente.post(
            "/usuarios",
            json={"nombre_usuario": "ana", "cedula": cedula, "contrasena": CONTRASENA},
        ),
        # Cédula inválida con forma de dato real.
        cliente.post(
            "/usuarios",
            json={
                "nombre_usuario": "eva",
                "cedula": cedula + "x",
                "contrasena": CONTRASENA,
            },
        ),
        # Contraseña inválida.
        cliente.post(
            "/usuarios",
            json={
                "nombre_usuario": "eva",
                "cedula": "3000003",
                "contrasena": CONTRASENA * 9,
            },
        ),
        cliente.post(
            "/sesiones", json={"nombre_usuario": "ana", "contrasena": "malaaaaaaa"}
        ),
        # Token con un carácter extra y token mal formado.
        cliente.get("/cuenta", headers={"Authorization": f"Bearer {token}x"}),
        cliente.get("/cuenta", headers={"Authorization": f"Token {token}"}),
        cliente.post("/cargas", json={"monto": "1"}, headers=ana),
    ]
    for r in respuestas:
        assert r.status_code >= 400
        for secreto in (cedula, token, CONTRASENA, "malaaaaaaa", "postgresql"):
            assert secreto not in r.text, (r.status_code, r.text)


def test_cors_permite_origen_configurado(cliente):
    r = cliente.get("/health", headers={"Origin": "http://localhost:4200"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:4200"


def test_cors_rechaza_otro_origen(cliente):
    r = cliente.get("/health", headers={"Origin": "http://malo.example"})
    assert "access-control-allow-origin" not in r.headers


def test_cors_preflight_permite_idempotency_key(cliente):
    r = cliente.options(
        "/cargas",
        headers={
            "Origin": "http://localhost:4200",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,idempotency-key,content-type",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:4200"


def test_testclient_sin_advertencia_de_deprecacion():
    # StarletteDeprecationWarning hereda de UserWarning, no de DeprecationWarning:
    # -W error convierte cualquier advertencia en error.
    resultado = subprocess.run(
        [sys.executable, "-W", "error", "-c", "import fastapi.testclient"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert resultado.returncode == 0, resultado.stderr[-500:]
