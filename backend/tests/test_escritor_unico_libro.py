"""Solo services/libro.py escribe en el libro (regla 2 del dinero)."""

import re
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
LIBRO = APP / "services" / "libro.py"
ESCRITURAS = re.compile(
    r"insert\s*\(\s*(Transaccion|Movimiento)\b"
    r"|INSERT\s+INTO\s+(transacciones|movimientos)\b"
    r"|update\s*\(\s*Cuenta\b"
    r"|UPDATE\s+cuentas\b"
    r"|Cuenta\.saldo\s*\+"
    r"|\.saldo\s*=[^=]",
    re.IGNORECASE,
)


def escrituras(fuente: str) -> list[str]:
    return [m.group(0) for m in ESCRITURAS.finditer(fuente)]


def test_detector_ve_las_escrituras():
    for fuente in [
        "insert(Transaccion).values()",
        "INSERT INTO movimientos (a) VALUES (1)",
        "update(Cuenta).values(saldo=Cuenta.saldo + d)",
        "UPDATE cuentas SET saldo = saldo + :d",
        "cuenta.saldo = 5",
    ]:
        assert escrituras(fuente), fuente


def test_libro_escribe_transacciones_movimientos_y_saldo():
    assert escrituras(LIBRO.read_text(encoding="utf-8"))


def test_solo_libro_escribe_transacciones_movimientos_y_saldo():
    problemas = [
        f"{ruta.relative_to(APP)}: {hallazgo}"
        for ruta in sorted(APP.rglob("*.py"))
        if ruta != LIBRO and "migraciones" not in ruta.parts
        for hallazgo in escrituras(ruta.read_text(encoding="utf-8"))
    ]
    assert problemas == []
