# Stack del reto: justificación y guía de estudio

Este documento lista **solo lo que se usó en Cuadre**, con la versión fijada en el repo, para qué se usó y por qué se eligió. Las versiones salen de `backend/requirements.lock.txt`, `frontend/package.json`, `docker-compose.yml` y el `Dockerfile`. Las reglas de uso de cada pieza están en `AGENTS.md` y `SPEC.md`.

> Las marcas **[CONFIRMAR]** son datos que no pude verificar en los archivos del repo. Revísalas antes de entregar.

## 1. Resumen del stack

| Capa | Herramienta | Versión | Para qué se usó |
| --- | --- | --- | --- |
| Lenguaje | Python | 3.12 | Todo el backend |
| API web | FastAPI | 0.162.4 | Endpoints síncronos, documentación interactiva en `/docs` y CORS para el frontend |
| Servidor | Uvicorn | 0.54.0 | Sirve la API, con un solo worker |
| Validación | Pydantic (modo estricto) | 2.14.3 | Rechazar montos y datos inválidos en la entrada |
| Configuración | pydantic-settings | 2.16.2 | Leer `DATABASE_URL`, `TEST_DATABASE_URL` y los parámetros de scrypt desde el entorno y el `.env` |
| Base de datos | PostgreSQL | 17 | Libro contable, transacciones, bloqueos y restricciones |
| Acceso a datos | SQLAlchemy | 2.1.8 | Sesiones, consultas, transacciones y bloqueos de filas |
| Driver | psycopg | 3.3.8 (binary) | Conexión de SQLAlchemy con PostgreSQL |
| Migraciones | Alembic | 1.20.1 | Versionar el esquema; la API migra al arrancar |
| Pruebas | pytest | 9.2.0 | Pruebas de dominio, base, servicios, API, concurrencia y barrido |
| Pruebas | Hypothesis | 6.170.15 | Propiedades de la división de bolsas |
| Pruebas | httpx | 0.28.1 | Cliente HTTP para las pruebas de la API |
| Calidad | Ruff | 0.17.4 | Lint y formato del backend |
| Seguridad | `hashlib.scrypt`, `secrets`, `hmac` | Librería estándar | Contraseñas, tokens y comparación en tiempo constante |
| Contenedores | Docker y Docker Compose | Compose v2 | PostgreSQL y API con un comando |
| Automatización | Makefile | — | `make up`, `seed`, `check`, `vencer`, `test` y `front` |
| Frontend | Angular | 22.2.5 | Interfaz de la demo |
| Frontend | TypeScript | 6.0.3 | Lenguaje del frontend |
| Frontend | RxJS | 7.8 | Peticiones HTTP y flujos de datos de Angular |
| Frontend | Vitest y jsdom | 5.0.5 y 30.1.3 | Pruebas unitarias del frontend (`ng test`) |
| Frontend | Prettier | 3.9.10 | Formato del frontend |
| Entorno | Node.js y npm | 24.19.0 y 12.0.2 | Compilar y servir el frontend |
| Control de versiones | Git y GitHub | — | Historial, un commit por tarea |
| IA | Claude (chat), Claude Code y Kiro | — | Diseño y revisión, implementación y auditoría |

## 2. Por qué este stack: los criterios

Elegí con seis criterios, en este orden de peso:

1. **Alineación con HabiCapital.** Su documento describe backend en Python, bases de datos relacionales y frontend en JavaScript o TypeScript. Usar lo mismo me acerca a lo que van a revisar.
2. **Garantías para el dinero.** Necesito transacciones atómicas, bloqueo de filas y restricciones en la base. Si mi código falla, la base debe impedir un saldo negativo o un movimiento duplicado.
3. **Qué tan bien me asiste la IA.** Las herramientas populares tienen buena data de entrenamiento: el código que generan es más fiable y me dan más ayuda.
4. **Lo que ya sé.** Domino Python, SQL, Git y Angular. Una herramienta que ya uso me deja más tiempo para lo importante.
5. **Tiempo.** Son 72 horas. Prefiero librerías maduras y con poca configuración.
6. **Poder explicarlo.** En la entrevista haré pair programming sobre mi código. Cada pieza debe ser algo que pueda defender.

## 3. Justificación herramienta por herramienta

### Backend

| Herramienta | Dónde se usa y por qué la elegí | Límite que reconozco |
| --- | --- | --- |
| **Python 3.12** | Es el lenguaje de backend de HabiCapital. Sus enteros no se desbordan, ideal para pesos. Tiene un gran ecosistema de pruebas. La imagen de Docker es `python:3.12-slim`. | Es más lento que un lenguaje compilado, irrelevante a esta escala. |
| **FastAPI** | Endpoints delgados que validan la forma y delegan al servicio. La documentación en `/docs` me sirve para la demo (inicio de sesión con `POST /sesiones` y botón **Authorize**). Los endpoints son síncronos (`def`) para que cada petición use su propia sesión y transacción. Además agrega CORS para `http://localhost:4200`. | No trae ORM ni panel de administración: elijo y conecto cada pieza yo mismo. |
| **Uvicorn** | Servidor de la API, con **un solo worker**. Arranca con `alembic upgrade head && uvicorn ...` en el contenedor. | Con varios workers, el diseño supone otro reloj y otro barrido; no lo probé (SPEC 11.2). |
| **Pydantic estricto** | Con `strict=True` y `extra="forbid"`, rechaza `1000.0`, `"1000"`, `1e3`, `true` y campos desconocidos con 422. Los patrones se validan contra el texto completo, no con `re.match` y `$`. | Valida la forma, no las reglas de negocio; esas viven en `domain/`. |
| **pydantic-settings** | Lee la configuración del entorno y del `.env` de la raíz. La clase `Configuracion` oculta su contenido al imprimirse, porque lleva credenciales. | Es una dependencia más para algo que podría hacerse con `os.environ`. La uso porque valida tipos y centraliza los valores por defecto. |
| **PostgreSQL 17** | Transacciones ACID, bloqueo de filas (`FOR UPDATE` en la bolsa y `FOR NO KEY UPDATE` en las cuentas), `CHECK`, `UNIQUE`, índices únicos parciales y llaves foráneas. Es la última defensa: impide estados inválidos aunque mi código falle. Las 19 invariantes del libro son consultas SQL. | Necesita un servidor (lo resuelve Docker), y un bloqueo mal ordenado o mal elegido causa deadlocks. |
| **SQLAlchemy 2 (síncrono)** | Control fino de transacciones y de bloqueos: `with_for_update(key_share=True)` para las cuentas, `populate_existing` en toda lectura con bloqueo. El servicio es dueño de la transacción. | Su mapa de identidad puede devolver un objeto viejo aunque la fila esté bloqueada: lo encontró la auditoría (H1). Por eso el saldo solo cambia con `saldo = saldo + :delta`. |
| **psycopg 3** | Driver de PostgreSQL. Expone el `sqlstate` del error, que uso para reintentar solo ante `40P01` (deadlock) y `40001` (serialización), sin depender del texto del mensaje. | Sus errores pueden traer la URL de la base: por eso ningún log ni mensaje los imprime. |
| **Alembic** | Migraciones versionadas. Al arrancar la API corre `alembic upgrade head`, y las pruebas crean `cuadre_test` desde cero con las mismas migraciones. | Curva de aprendizaje; una migración mal escrita es difícil de revertir. |

### Pruebas y calidad

| Herramienta | Dónde se usa y por qué la elegí | Límite que reconozco |
| --- | --- | --- |
| **pytest** | Es el estándar. Un fixture crea `cuadre_test`, la migra y la borra al terminar. El fixture `bd` corre las 19 invariantes al final de cada prueba con base de datos. `--strict-markers` impide que un `@pytest.mark.sin_invariantes` mal escrito apague las invariantes sin avisar. | La concurrencia no es determinista: la pruebo con pruebas secuenciales que fijan el orden y con hilos contra una base real. |
| **Hypothesis** | Genera casos que no se me ocurrirían. Prueba, para la división de bolsas, que la suma de las partes es igual al total, que toda parte es mayor que 0 y que la diferencia del creador está entre 0 y 49. | Solo cubre el dominio puro, no la base de datos. |
| **httpx** | Cliente HTTP que usan las pruebas de la API. `AGENTS.md` lo lista en el stack. **[CONFIRMAR: `requirements-dev.txt` también lista `httpx2`; revisa si hace falta]** | — |
| **Ruff** | Lint y formato con una sola herramienta. Es parte de la definición de hecho de cada tarea: suite en verde y Ruff limpio. | Solo revisa estilo y errores simples, no la lógica. |
| **`threading` y `threading.Barrier`** (estándar) | Las pruebas de concurrencia arrancan los hilos a la vez, sin `sleep`. La barrera tiene un tiempo máximo para que una prueba colgada falle en vez de bloquearse. | El solapamiento real depende de la contención; por eso se repiten y se aumentó el número de tareas. |
| **`ast`** (estándar) | Una prueba revisa con `ast` que `domain/` no importe SQLAlchemy ni FastAPI, y que `domain/` y `services/` no lean el reloj. | Solo detecta los patrones que le indico. |

### Seguridad (librería estándar, sin dependencias)

| Herramienta | Dónde se usa y por qué la elegí | Límite que reconozco |
| --- | --- | --- |
| **`hashlib.scrypt`** | Hash lento de la contraseña, con sal de 16 bytes. Parámetros mínimos de OWASP (N = 2^17, r = 8, p = 1), guardados dentro del hash para subir el costo sin invalidar los viejos. Las pruebas usan N = 2^14 para que la suite sea rápida. | No soy experto en seguridad: sigo la recomendación y lo declaro. |
| **`secrets`** | Genera el token de sesión con `token_urlsafe(32)`. Solo se guarda su SHA-256, así que si se filtra la tabla de sesiones, los tokens no sirven. | No hay defensa contra fuerza bruta ni contra enumeración de usuarios por tiempo (límite declarado). |
| **`hmac.compare_digest`** | Compara el hash de la contraseña en tiempo constante. | — |

### Infraestructura y automatización

| Herramienta | Dónde se usa y por qué la elegí | Límite que reconozco |
| --- | --- | --- |
| **Docker y Docker Compose** | Quien evalúa corre todo con un comando, sin instalar nada. Compose levanta `db` (PostgreSQL 17, con volumen `pgdata` y `healthcheck`) y `api`, que espera a que la base esté sana. El contenedor de la API corre con un usuario que no es root, con las versiones fijadas del lock y con los puertos publicados solo en `127.0.0.1`. | Si Docker falla en la máquina de quien evalúa, no arranca. |
| **Makefile** | Un solo punto de entrada: `make up`, `make seed`, `make check`, `make vencer`, `make test` y `make front`. | Es una capa más que hay que mantener junto al README. |
| **`.env` y `.env.example`** | Las credenciales viven en `.env`, que no se sube al repo; `.env.example` solo trae los nombres de las variables. Los agentes no pueden leer `.env`. | Si los valores no coinciden entre `POSTGRES_*` y las URL, la API no conecta. |
| **Git y GitHub** | Un commit pequeño por tarea en verde, que sirve como punto seguro para volver atrás. | — |

### Frontend

| Herramienta | Dónde se usa y por qué la elegí | Límite que reconozco |
| --- | --- | --- |
| **Angular 22** | HabiCapital usa JavaScript o TypeScript en el frontend, y Angular es el framework que domino, así que puedo explicar cada línea. Usa componentes independientes (standalone), un interceptor que agrega el token a cada petición, un guard de rutas y un servicio que conserva la clave de idempotencia para reintentar. | Tiene más estructura inicial que otras opciones. Solo muestra datos y nunca calcula dinero. |
| **TypeScript** | Tipado estricto para los montos y las respuestas de la API. | — |
| **RxJS** | Es la base de las peticiones HTTP de Angular. | — |
| **Vitest y jsdom** | Pruebas unitarias del frontend con `ng test`. jsdom simula el navegador. | Pruebas unitarias, no de punta a punta: no recorren la app en un navegador real. |
| **Prettier** | Formato consistente del frontend. | — |
| **Node.js 24 y npm 12** | Compilan y sirven el frontend (`make front`, que instala con `npm ci` si falta `node_modules`). Las versiones están fijadas en `package-lock.json`. | — |
| **`sessionStorage`** (navegador) | Guarda el token de sesión por pestaña, así se pueden abrir varios usuarios a la vez. | Es vulnerable a XSS; riesgo aceptado para el reto. |

### Herramientas de IA

| Herramienta | Para qué se usó | Límite que reconozco |
| --- | --- | --- |
| **Claude (chat)** | Diseño de la arquitectura y del `SPEC.md` por bloques, y revisión de cada entrega contra `SPEC.md`, `AGENTS.md` y `DECISIONS.md`. | Propuso relaciones más complejas de lo necesario (`AI_LOG`, 11-nov) y una regla de bloqueo que no garantizaba nada (H1). |
| **Claude Code** | Escribió el código y los planes, tarea por tarea, con el ciclo de `docs/FLUJO.md`: plan, pruebas en rojo, implementación, reporte y commit. | Una vez cambió un `assert` sin detenerse (T12). Por eso la regla de detenerse antes de tocar una prueba aprobada. |
| **Kiro** | Auditoría en sesión aparte, después de las tareas que mueven dinero. Lee `AGENTS.md` automáticamente. **[CONFIRMAR qué modelo hizo la auditoría del SPEC y si Kiro auditó T6, T11 y T14]** | No sustituye mi revisión. |
| **`AGENTS.md`, `CLAUDE.md` y los atajos de `.claude/commands/`** | Dejan escritas las reglas del dinero y el protocolo de trabajo, para que ningún agente improvise. | Un agente puede ignorarlas; por eso las pruebas y las invariantes verifican lo importante. |

## 4. Alternativas que descarté

Son opciones válidas en otros contextos. Las descarto por este reto concreto.

| Alternativa | Por qué no la uso |
| --- | --- |
| Django | Es completo pero pesado. Su ORM y su panel esconden justo lo que quiero controlar. |
| Flask | No trae validación ni documentación; las reconstruiría a mano. |
| Spring Boot (Java) | Lo domino menos que Python y escribo más lento con él. |
| Node con TypeScript en el backend | HabiCapital usa Python en el backend y cambiar de lenguaje no aporta nada en 72 horas. |
| React con Vite | Era el plan inicial, pero conozco Angular y no React; no podría defender el código en la entrevista. |
| MongoDB u otra base no relacional | Da menos garantías declarativas (restricciones y llaves foráneas), y la partida doble es un modelo relacional. |
| SQLite | No reproduce la concurrencia real de producción. PostgreSQL sí. |
| JWT | Un token aleatorio guardado como hash permite revocar la sesión y no agrega dependencias. |
| Aislamiento `SERIALIZABLE` | Obligaría a reintentar muchas transacciones; con `READ COMMITTED` y bloqueos explícitos controlo qué se serializa. |
| Celery, Redis o colas de mensajes | Agregan infraestructura para algo que resuelve una función. El barrido es `procesar_vencidas`, que se ejecuta con `make vencer` y usa el estado de la base como cola. |
| Microservicios | En 72 horas, un monolito modular con capas claras es más seguro de probar. |
| Terraform | HabiCapital lo menciona, pero no aporta a la pregunta del reto. |

## 5. Previsto en el diseño, pero que no se usó

Para que el documento no prometa más de lo que hay:

- **Hilo del barrido en el `lifespan` de FastAPI.** El diseño original lo incluía; el recorte 3 lo reemplazó por `make vencer` (`app/vencer.py`).
- **GitHub Actions con PostgreSQL como servicio.** `SPEC.md` (sección 10.8) lo prevé y el roadmap lo dejaba "solo si sobra tiempo". **[CONFIRMAR: si existe `.github/workflows/`, agrégalo a la tabla de infraestructura; si no, déjalo como mejora futura]**
- **Pruebas de mutación automáticas.** Se rompió el código a propósito a mano (bloqueo de la bolsa y del barrido), sin una herramienta.

## 6. Qué debo saber explicar de cada pieza

Las preguntas de la entrevista suelen tocar el porqué, no el cómo. Estas son las que debo poder responder sin mirar el código:

| Pieza | Pregunta | Idea central |
| --- | --- | --- |
| PostgreSQL | ¿Por qué `FOR NO KEY UPDATE` en las cuentas y `FOR UPDATE` en la bolsa? | `FOR NO KEY UPDATE` no choca con el `FOR KEY SHARE` que toman las llaves foráneas al insertar movimientos. La bolsa usa `FOR UPDATE` porque serializa todas las operaciones sobre ella. |
| PostgreSQL | ¿Qué impediría un aporte duplicado aunque mi código falle? | El índice único parcial de un aporte por participante y bolsa. |
| SQLAlchemy | ¿Qué hace `populate_existing` y por qué lo necesito? | SQLAlchemy no refresca un objeto que ya está en la sesión: sin esa opción, la fila quedaría bloqueada pero yo leería un saldo viejo. |
| SQL | ¿Por qué `saldo = saldo + :delta` y no calcular el saldo en Python? | Si dos operaciones leen el mismo saldo y escriben su resultado, una pisa a la otra. El `UPDATE` relativo lo resuelve dentro de la base. |
| PostgreSQL | ¿Por qué `INSERT ... ON CONFLICT` en la idempotencia y no `SELECT` y luego `INSERT`? | Entre el `SELECT` y el `INSERT` puede colarse otra petición con la misma clave. `ON CONFLICT` es atómico. |
| PostgreSQL | ¿Por qué ordenar los bloqueos por id? | Con un orden único, dos operaciones no pueden esperarse en ciclo (deadlock). |
| pytest e invariantes | ¿Cómo sé que mis pruebas de concurrencia no pasan por suerte? | Quité el `FOR UPDATE` de la bolsa y fallaron 60 de 90 casos. Cada invariante tiene además una prueba que introduce una violación a propósito. |
| Pydantic | ¿Por qué modo estricto? | Un monto con decimales o un texto nunca se convierte en silencio: se rechaza con 422. |
| FastAPI | ¿Por qué endpoints síncronos? | Cada petición usa su propia sesión y su propia transacción, sin mezclar `async` con una base síncrona. |
| scrypt | ¿Por qué un hash lento para contraseñas y SHA-256 para tokens? | Las personas eligen contraseñas adivinables, así que el hash debe ser caro; el token es aleatorio y larguísimo, y no hay nada que adivinar. |
| Alembic | ¿Cómo se crea la base de pruebas? | `cuadre_test` se crea de cero con las migraciones reales al empezar `pytest` y se borra al terminar. Una guarda rechaza cualquier base cuyo nombre no termine en `_test`. |
| Docker | ¿Qué hace el contenedor de la API al arrancar? | Corre `alembic upgrade head` y luego `uvicorn` con un solo worker, con un usuario que no es root. |
| Angular | ¿Qué hace el frontend antes de aportar o confirmar? | Vuelve a consultar la bolsa y avisa si la meta o la parte cambiaron, porque el backend no verifica qué términos vio el usuario. |

