"""Invariantes de SPEC 4 y el comando de `make check`.

Cada invariante es una consulta de solo lectura que devuelve las filas que la
violan: cero filas significa que se cumple. El SQL es copia literal de SPEC 4;
una prueba lo compara con el documento.

Uso: `python -m app.db.invariantes` corre todas contra la base de desarrollo
(DATABASE_URL). Ningún mensaje incluye la URL ni el texto de un error, porque
el de psycopg puede traer el host y el usuario.
"""

import sys
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Engine, text

from app.db.sesion import obtener_motor

Filas = list[tuple[Any, ...]]


@dataclass(frozen=True)
class Invariante:
    id: str
    descripcion: str
    sql: str
    # Columnas que forman el id que se imprime (2 en L7 y en B9).
    columnas_id: int = 1


INVARIANTES: tuple[Invariante, ...] = (
    Invariante(
        "L1",
        "Cada transacción tiene exactamente dos movimientos",
        """
SELECT t.id
FROM transacciones t
LEFT JOIN movimientos m ON m.transaccion_id = t.id
GROUP BY t.id
HAVING count(m.cuenta_id) <> 2;
""",
    ),
    Invariante(
        "L2",
        "Las patas coinciden con la cabecera: −monto en el origen y +monto en el "
        "destino",
        """
SELECT t.id
FROM transacciones t
WHERE NOT EXISTS (
        SELECT 1 FROM movimientos m
        WHERE m.transaccion_id = t.id
          AND m.cuenta_id = t.cuenta_origen_id
          AND m.monto = -t.monto)
   OR NOT EXISTS (
        SELECT 1 FROM movimientos m
        WHERE m.transaccion_id = t.id
          AND m.cuenta_id = t.cuenta_destino_id
          AND m.monto = t.monto);
""",
    ),
    Invariante(
        "L3",
        "El saldo de cada cuenta es igual a la suma de sus movimientos",
        """
SELECT c.id, c.saldo, COALESCE(sum(m.monto), 0) AS suma_movimientos
FROM cuentas c
LEFT JOIN movimientos m ON m.cuenta_id = c.id
GROUP BY c.id, c.saldo
HAVING c.saldo <> COALESCE(sum(m.monto), 0);
""",
    ),
    Invariante(
        "L4",
        "La suma de todos los saldos es cero",
        """
SELECT sum(saldo) AS suma_saldos
FROM cuentas
HAVING sum(saldo) <> 0;
""",
    ),
    Invariante(
        "L5",
        "Cada transacción respeta los tipos de cuenta de la tabla 3.5",
        """
SELECT t.id, t.tipo, o.tipo AS tipo_origen, d.tipo AS tipo_destino
FROM transacciones t
JOIN cuentas o ON o.id = t.cuenta_origen_id
JOIN cuentas d ON d.id = t.cuenta_destino_id
WHERE (t.tipo, o.tipo, d.tipo) NOT IN (VALUES
    ('carga', 'sistema', 'personal'),
    ('transferencia', 'personal', 'personal'),
    ('aporte', 'personal', 'bolsa'),
    ('devolucion', 'bolsa', 'personal'),
    ('transferencia_final', 'bolsa', 'personal'));
""",
    ),
    Invariante(
        "L6",
        "Toda cuenta personal tiene usuario y toda cuenta de bolsa tiene su bolsa",
        """
SELECT c.id
FROM cuentas c
LEFT JOIN usuarios u ON u.cuenta_id = c.id
LEFT JOIN bolsas b ON b.cuenta_id = c.id
WHERE (c.tipo = 'personal' AND u.id IS NULL)
   OR (c.tipo = 'bolsa' AND b.id IS NULL);
""",
    ),
    Invariante(
        "L7",
        "Cada clave de idempotencia es coherente con su transacción",
        """
SELECT k.cuenta_solicitante_id, k.clave, k.operacion
FROM claves_idempotencia k
LEFT JOIN transacciones t ON t.id = k.transaccion_id
WHERE (
       (k.operacion = 'cargar'     AND t.tipo = 'carga'         AND t.cuenta_destino_id = k.cuenta_solicitante_id)
    OR (k.operacion = 'transferir' AND t.tipo = 'transferencia' AND t.cuenta_origen_id  = k.cuenta_solicitante_id)
    OR (k.operacion = 'aportar'    AND t.tipo = 'aporte'        AND t.cuenta_origen_id  = k.cuenta_solicitante_id)
    OR (k.operacion = 'retirarse'  AND (t.id IS NULL
          OR (t.tipo = 'devolucion' AND t.cuenta_destino_id = k.cuenta_solicitante_id)))
) IS NOT TRUE;
""",
        columnas_id=2,
    ),
    Invariante(
        "L8",
        "Ninguna carga, transferencia ni aporte supera el tope",
        """
SELECT t.id, t.tipo, t.monto
FROM transacciones t
WHERE t.tipo IN ('carga', 'transferencia', 'aporte')
  AND t.monto > 50000000;
""",
    ),
    Invariante(
        "B1",
        "Cada bolsa tiene entre 2 y 50 participantes",
        """
SELECT b.id
FROM bolsas b
LEFT JOIN participantes p ON p.bolsa_id = b.id
GROUP BY b.id
HAVING count(p.cuenta_id) NOT BETWEEN 2 AND 50;
""",
    ),
    Invariante(
        "B2",
        "El creador es participante",
        """
SELECT b.id
FROM bolsas b
WHERE NOT EXISTS (
    SELECT 1 FROM participantes p
    WHERE p.bolsa_id = b.id AND p.cuenta_id = b.creador_cuenta_id);
""",
    ),
    Invariante(
        "B3",
        "Las partes respetan la división y el total",
        """
WITH n AS (
    SELECT bolsa_id, count(*) AS n, sum(parte) AS suma
    FROM participantes
    GROUP BY bolsa_id
)
SELECT b.id
FROM bolsas b
JOIN n ON n.bolsa_id = b.id
WHERE n.suma <> b.total
   OR b.total > n.n * 49990000
   OR EXISTS (
        SELECT 1 FROM participantes p
        WHERE p.bolsa_id = b.id
          AND p.parte <> CASE
                WHEN p.cuenta_id = b.creador_cuenta_id THEN b.total / n.n + b.total % n.n
                ELSE b.total / n.n
              END);
""",
    ),
    Invariante(
        "B4",
        "Cada aporte viene de un participante de esa bolsa y es exactamente su parte",
        """
SELECT t.id
FROM transacciones t
LEFT JOIN bolsas b ON b.cuenta_id = t.cuenta_destino_id
LEFT JOIN participantes p ON p.bolsa_id = b.id AND p.cuenta_id = t.cuenta_origen_id
WHERE t.tipo = 'aporte'
  AND (b.id IS NULL OR p.cuenta_id IS NULL OR t.monto <> p.parte);
""",
    ),
    Invariante(
        "B5",
        "Cada devolución va a un participante que aportó, por exactamente lo que "
        "aportó",
        """
SELECT t.id
FROM transacciones t
LEFT JOIN transacciones a
       ON a.tipo = 'aporte'
      AND a.cuenta_origen_id = t.cuenta_destino_id
      AND a.cuenta_destino_id = t.cuenta_origen_id
WHERE t.tipo = 'devolucion'
  AND (a.id IS NULL OR a.monto <> t.monto);
""",
    ),
    Invariante(
        "B6",
        "La transferencia final va a la cuenta objetivo por exactamente lo que "
        "quedaba, y la bolsa queda en cero",
        """
SELECT t.id
FROM transacciones t
LEFT JOIN bolsas b ON b.cuenta_id = t.cuenta_origen_id
LEFT JOIN cuentas c ON c.id = b.cuenta_id
WHERE t.tipo = 'transferencia_final'
  AND (b.id IS NULL
       OR t.cuenta_destino_id <> b.cuenta_objetivo_id
       OR c.saldo <> 0
       OR t.monto <> (
            SELECT COALESCE(sum(CASE WHEN x.tipo = 'aporte' THEN x.monto ELSE -x.monto END), 0)
            FROM transacciones x
            WHERE (x.tipo = 'aporte' AND x.cuenta_destino_id = b.cuenta_id)
               OR (x.tipo = 'devolucion' AND x.cuenta_origen_id = b.cuenta_id)));
""",
    ),
    Invariante(
        "B7",
        "Ningún aporte es posterior a la fecha límite",
        """
SELECT t.id
FROM transacciones t
JOIN bolsas b ON b.cuenta_id = t.cuenta_destino_id
WHERE t.tipo = 'aporte'
  AND t.creado_en >= b.fecha_limite;
""",
    ),
    Invariante(
        "B8",
        "Toda bolsa cerrada tiene saldo cero",
        """
SELECT b.id
FROM bolsas b
JOIN cuentas c ON c.id = b.cuenta_id
WHERE b.estado = 'cerrada'
  AND c.saldo <> 0;
""",
    ),
    Invariante(
        "B9",
        "El estado de cada participante coincide con el libro",
        """
WITH e AS (
    SELECT p.bolsa_id, p.cuenta_id, p.estado, b.estado AS estado_bolsa,
           b.transferir_al_vencer AS transferir,
           EXISTS (SELECT 1 FROM transacciones t
                   WHERE t.tipo = 'aporte'
                     AND t.cuenta_origen_id = p.cuenta_id
                     AND t.cuenta_destino_id = b.cuenta_id) AS aporto,
           EXISTS (SELECT 1 FROM transacciones t
                   WHERE t.tipo = 'devolucion'
                     AND t.cuenta_origen_id = b.cuenta_id
                     AND t.cuenta_destino_id = p.cuenta_id) AS devuelto
    FROM participantes p
    JOIN bolsas b ON b.id = p.bolsa_id
)
SELECT bolsa_id, cuenta_id, estado, estado_bolsa
FROM e
WHERE (estado = 'pendiente' AND (aporto OR estado_bolsa <> 'abierta'))
   OR (estado IN ('pagado', 'por_confirmar') AND (NOT aporto OR devuelto))
   OR (estado = 'por_confirmar' AND estado_bolsa NOT IN ('abierta', 'cancelada'))
   OR (estado = 'retirado' AND aporto AND NOT devuelto AND estado_bolsa <> 'liquidando')
   OR (estado = 'pagado' AND estado_bolsa = 'liquidando' AND NOT transferir);
""",
        columnas_id=2,
    ),
    Invariante(
        "B10",
        "El estado de la bolsa coincide con la transferencia final",
        """
SELECT b.id
FROM bolsas b
WHERE (b.estado <> 'cerrada'
       AND EXISTS (SELECT 1 FROM transacciones t
                   WHERE t.tipo = 'transferencia_final'
                     AND t.cuenta_origen_id = b.cuenta_id))
   OR (b.estado IN ('abierta', 'cancelada')
       AND NOT EXISTS (SELECT 1 FROM participantes p
                       WHERE p.bolsa_id = b.id
                         AND p.estado IN ('pendiente', 'por_confirmar')))
   OR (b.estado = 'cerrada'
       AND EXISTS (SELECT 1 FROM participantes p
                   WHERE p.bolsa_id = b.id AND p.estado = 'pagado')
       AND NOT EXISTS (SELECT 1 FROM transacciones t
                       WHERE t.tipo = 'transferencia_final'
                         AND t.cuenta_origen_id = b.cuenta_id));
""",
    ),
    Invariante(
        "B11",
        "Solo una bolsa con transferir_al_vencer puede estar cancelada",
        """
SELECT b.id
FROM bolsas b
WHERE b.estado = 'cancelada'
  AND NOT b.transferir_al_vencer;
""",
    ),
)

AVISO_ERROR = (
    "no se pudo consultar la base de desarrollo; ¿corriste alembic upgrade head?"
)


def correr_invariantes(
    motor: Engine, ids: Iterable[str] | None = None
) -> dict[str, Filas]:
    """Corre las invariantes pedidas (todas si `ids` es None) en una sola
    transacción REPEATABLE READ READ ONLY, y devuelve las filas de cada una.

    Una sola transacción hace que el reporte describa un mismo instante aunque
    haya operaciones en curso (SPEC 4.1); READ ONLY hace que PostgreSQL
    rechace cualquier escritura. Siempre termina con rollback.
    """
    elegidas = list(INVARIANTES)
    if ids is not None:
        por_id = {i.id: i for i in INVARIANTES}
        elegidas = [por_id[id] for id in ids]
    resultados: dict[str, Filas] = {}
    with motor.connect() as conexion, conexion.begin() as transaccion:
        conexion.execute(
            text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        )
        for invariante in elegidas:
            filas = conexion.execute(text(invariante.sql)).all()
            resultados[invariante.id] = [tuple(fila) for fila in filas]
        transaccion.rollback()
    return resultados


def violaciones(resultados: dict[str, Filas]) -> dict[str, Filas]:
    """Solo las invariantes que devolvieron alguna fila."""
    return {id: filas for id, filas in resultados.items() if filas}


def _columnas_id(id: str) -> int:
    for invariante in INVARIANTES:
        if invariante.id == id:
            return invariante.columnas_id
    return 1


def formatear_reporte(resultados: dict[str, Filas], maximo_ids: int = 5) -> list[str]:
    """Una línea por invariante: id, PASA o FALLA, filas y primeros ids.

    Los ids se ordenan para que "los primeros" no dependan del plan de la
    consulta.
    """
    lineas = []
    for id, filas in resultados.items():
        if not filas:
            lineas.append(f"{id:<4} PASA  0")
            continue
        columnas = _columnas_id(id)
        claves = sorted(fila[:columnas] for fila in filas)
        mostrados = ", ".join(
            "/".join(str(valor) for valor in clave) for clave in claves[:maximo_ids]
        )
        lineas.append(f"{id:<4} FALLA {len(filas)} {mostrados}")
    return lineas


def reportar(motor: Engine) -> int:
    """Imprime el reporte y devuelve el código de salida: 0, 1 o 2 (error).

    Ante cualquier excepción imprime solo su tipo: `str(error)` puede traer el
    host, el usuario o el SQL.
    """
    try:
        resultados = correr_invariantes(motor)
    except Exception as error:  # noqa: BLE001 (cualquier error sale como código 2)
        return _reportar_error(error)
    for linea in formatear_reporte(resultados):
        print(linea)
    fallidas = violaciones(resultados)
    if fallidas:
        print(f"FALLA: {len(fallidas)} de {len(resultados)} invariantes")
        return 1
    print(f"PASA: {len(resultados)} invariantes")
    return 0


def _reportar_error(error: Exception) -> int:
    print(f"ERROR ({type(error).__name__}): {AVISO_ERROR}", file=sys.stderr)
    return 2


def main() -> int:
    try:
        motor = obtener_motor()
    except Exception as error:  # noqa: BLE001 (cualquier error sale como código 2)
        return _reportar_error(error)
    return reportar(motor)


if __name__ == "__main__":
    sys.exit(main())
