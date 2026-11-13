"""Ejecución de operaciones en hilos para las pruebas de concurrencia (SPEC 10.4).

Diseño: `hilos` hilos de trabajo, cada uno con su propia sesión (y por tanto
su propia conexión del pool). Todos esperan en un único `threading.Barrier`
del tamaño del número de hilos y, al soltarse, toman tareas de una cola
compartida hasta vaciarla. Así la barrera se usa una sola vez, no hace falta
que el número de tareas sea múltiplo del de hilos, y nadie puede quedar
esperando a compañeros que nunca llegan. La barrera tiene timeout: si algo
se cuelga, la prueba falla en vez de bloquearse.
"""

import queue
import threading
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy.orm import Session, sessionmaker

from app.domain.errores import ErrorDominio

ESPERA_BARRERA_S = 10.0
ESPERA_HILO_S = 120.0

Tarea = Callable[[Session], object]


@dataclass
class Resultados:
    conteo: Counter[str] = field(default_factory=Counter)
    valores: list[object] = field(default_factory=list)
    inesperados: list[BaseException] = field(default_factory=list)


def correr_en_hilos(
    bd: sessionmaker[Session], tareas: list[Tarea], hilos: int
) -> Resultados:
    """Corre `tareas` con `hilos` hilos que arrancan a la vez.

    Cada resultado se clasifica como "ok" (y se guarda su valor) o como el
    `codigo` del ErrorDominio. Cualquier otra excepción va a `inesperados`.
    """
    assert 1 <= hilos <= len(tareas)
    pendientes: queue.SimpleQueue[Tarea] = queue.SimpleQueue()
    for tarea in tareas:
        pendientes.put(tarea)
    barrera = threading.Barrier(hilos, timeout=ESPERA_BARRERA_S)
    resultados = Resultados()
    cerrojo = threading.Lock()  # solo protege `resultados` de la prueba

    def anotar(clave: str | None, valor: object = None, error=None) -> None:
        with cerrojo:
            if error is not None:
                resultados.inesperados.append(error)
                return
            resultados.conteo[clave] += 1
            if clave == "ok":
                resultados.valores.append(valor)

    def trabajar() -> None:
        try:
            with bd() as sesion:
                barrera.wait()
                while True:
                    try:
                        tarea = pendientes.get_nowait()
                    except queue.Empty:
                        return
                    try:
                        anotar("ok", tarea(sesion))
                    except ErrorDominio as error:
                        anotar(error.codigo)
        except BaseException as error:  # noqa: BLE001 - se reporta en la prueba
            anotar(None, error=error)

    trabajadores = [threading.Thread(target=trabajar) for _ in range(hilos)]
    for hilo in trabajadores:
        hilo.start()
    for hilo in trabajadores:
        hilo.join(ESPERA_HILO_S)
        assert not hilo.is_alive(), "un hilo no terminó a tiempo"
    assert resultados.inesperados == [], resultados.inesperados
    return resultados
