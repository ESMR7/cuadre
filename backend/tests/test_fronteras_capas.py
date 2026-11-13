"""Fronteras de capas (SPEC 2.1) y reloj prohibido en domain/ y services/.

Se revisan con `ast` todos los archivos de cada paquete (`rglob`), incluidos
los imports dentro de funciones o de `if TYPE_CHECKING`.
"""

import ast
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parent.parent / "app"
PROHIBIDOS_DOMAIN = {"sqlalchemy", "fastapi", "starlette", "psycopg"}
PROHIBIDOS_SERVICES = {"fastapi", "starlette"}
ATRIBUTOS_DE_RELOJ = {"now", "utcnow", "today"}


def importaciones_prohibidas(fuente: str, prohibidos: set[str]) -> list[str]:
    """Módulos prohibidos importados en cualquier parte del texto."""
    encontrados: list[str] = []
    for nodo in ast.walk(ast.parse(fuente)):
        if isinstance(nodo, ast.Import):
            modulos = [alias.name for alias in nodo.names]
        elif isinstance(nodo, ast.ImportFrom):
            # nivel > 0 son imports relativos internos: no son librerías externas.
            modulos = [nodo.module or ""] if nodo.level == 0 else []
        else:
            continue
        encontrados += [m for m in modulos if m.split(".")[0] in prohibidos]
    return encontrados


def llamadas_de_reloj(fuente: str) -> list[str]:
    """Llamadas a .now(, .utcnow(, .today( o time.time(."""
    encontradas: list[str] = []
    for nodo in ast.walk(ast.parse(fuente)):
        if not (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute)):
            continue
        atributo = nodo.func.attr
        es_time_time = (
            atributo == "time"
            and isinstance(nodo.func.value, ast.Name)
            and nodo.func.value.id == "time"
        )
        if atributo in ATRIBUTOS_DE_RELOJ or es_time_time:
            encontradas.append(f"{atributo}() en la línea {nodo.lineno}")
    return encontradas


def archivos(paquete: str) -> list[Path]:
    return sorted((APP / paquete).rglob("*.py"))


def revisar(paquete: str, funcion, *argumentos) -> list[str]:
    problemas: list[str] = []
    for ruta in archivos(paquete):
        for hallazgo in funcion(ruta.read_text(encoding="utf-8"), *argumentos):
            problemas.append(f"{ruta.relative_to(APP)}: {hallazgo}")
    return problemas


def test_domain_existe_y_tiene_archivos():
    # Evita que las pruebas de abajo pasen en vacío.
    assert len(archivos("domain")) >= 4


def test_domain_no_importa_sqlalchemy_ni_fastapi():
    assert revisar("domain", importaciones_prohibidas, PROHIBIDOS_DOMAIN) == []


def test_services_no_importa_fastapi():
    # services/ aún no existe: sin archivos no hay nada que revisar.
    assert revisar("services", importaciones_prohibidas, PROHIBIDOS_SERVICES) == []


def test_domain_no_lee_el_reloj():
    assert revisar("domain", llamadas_de_reloj) == []


def test_services_no_lee_el_reloj():
    assert revisar("services", llamadas_de_reloj) == []


@pytest.mark.parametrize(
    "fuente",
    [
        "import sqlalchemy",
        "from sqlalchemy.orm import Session",
        "def f():\n    from sqlalchemy import text\n",
        "if TYPE_CHECKING:\n    import fastapi\n",
        "from starlette.requests import Request",
        "import psycopg.errors",
    ],
)
def test_detector_de_imports_ve_los_prohibidos(fuente):
    assert importaciones_prohibidas(fuente, PROHIBIDOS_DOMAIN)


def test_detector_de_imports_ignora_los_permitidos():
    fuente = "import enum\nfrom app.domain import errores\nfrom . import x\n"
    assert importaciones_prohibidas(fuente, PROHIBIDOS_DOMAIN) == []


@pytest.mark.parametrize(
    "fuente",
    [
        "from datetime import datetime\nx = datetime.now()",
        "import datetime\nx = datetime.datetime.utcnow()",
        "from datetime import date\nx = date.today()",
        "import time\nx = time.time()",
        "def f():\n    return datetime.now(tz)\n",
    ],
)
def test_detector_de_reloj_ve_las_llamadas(fuente):
    assert llamadas_de_reloj(fuente)


def test_detector_de_reloj_ignora_codigo_sin_reloj():
    fuente = "def f(ahora):\n    return ahora.isoformat()\n"
    assert llamadas_de_reloj(fuente) == []
