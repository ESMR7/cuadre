# Stack del reto: justificación y guía de estudio

Uso Python, FastAPI y PostgreSQL porque es el stack que HabiCapital declara en producción, el más sólido para mover dinero con garantías transaccionales y el que mejor entiende la IA que me asiste. Las versiones exactas no están fijadas aquí: confirma la vigente en la documentación oficial de cada herramienta. Las reglas de uso de cada pieza están en `AGENTS.md` y `SPEC.md`; esta guía explica por qué las elegí y qué debo estudiar.

## 1. Resumen del stack

| Capa | Herramienta | Para qué la uso | Estudio |
| --- | --- | --- | --- |
| Lenguaje | Python 3 | Toda la lógica del backend | Ya lo uso |
| API web | FastAPI | Endpoints, validación y documentación interactiva | Alto |
| Validación | Pydantic (modo estricto) | Rechazar montos y datos inválidos en la entrada | Alto |
| Base de datos | PostgreSQL | Libro contable, transacciones, bloqueos y restricciones | Alto |
| Acceso a datos | SQLAlchemy 2 | Modelos, consultas y control de transacciones y bloqueos | Alto |
| Migraciones | Alembic | Versionar el esquema de la base | Medio |
| Pruebas | pytest y Hypothesis | Pruebas normales, de propiedades y de concurrencia | Alto |
| Seguridad | `hashlib.scrypt`, `secrets` y `hmac` (librería estándar) | Contraseñas con hash lento y tokens aleatorios, sin dependencias | Medio |
| Contenedores | Docker y Docker Compose | Correr todo con un comando | Medio |
| Frontend | Angular y TypeScript | Demo mínima, solo si alcanza el tiempo | Ya lo uso |
| Automatización | Makefile y GitHub Actions | Comandos y pruebas en cada push | Bajo |

## 2. Por qué este stack: los criterios

Elegí con seis criterios, en este orden de peso:

1. **Alineación con HabiCapital.** Su documento describe backend en Python, bases de datos relacionales y frontend en JavaScript o TypeScript. Usar lo mismo me acerca a lo que van a revisar y a lo que haría en el cargo.
2. **Garantías para el dinero.** Necesito transacciones atómicas, bloqueo de filas y restricciones en la base de datos. Si mi código falla, la base debe impedir un saldo negativo o un movimiento duplicado.
3. **Qué tan bien me asiste la IA.** Su documento dice que el stack se eligió para que los modelos tengan buena data de entrenamiento. Las herramientas populares generan código más fiable y me dan más ayuda.
4. **Lo que ya sé.** Domino Python, SQL, Git y Angular. Java y Spring Boot los conozco menos. Una herramienta que ya uso me deja más tiempo para lo importante.
5. **Tiempo.** Son 72 horas. Prefiero librerías maduras y con poca configuración.
6. **Poder explicarlo.** En la entrevista haré pair programming sobre mi código. Cada pieza debe ser algo que pueda defender.

## 3. Justificación herramienta por herramienta

Cada herramienta tiene una razón y un límite que debo reconocer, porque en la entrevista me preguntarán por ambos.

| Herramienta | Por qué la elijo | Límite que reconozco |
| --- | --- | --- |
| Python | Es el lenguaje de backend de HabiCapital. Sus enteros no se desbordan, ideal para pesos. Tiene un gran ecosistema de pruebas. | Es más lento que un lenguaje compilado, algo irrelevante a esta escala. |
| FastAPI | Valida entradas con Pydantic y genera documentación interactiva que me sirve para la demo. Su tipado explícito ayuda a la IA y a mí. | No trae ORM ni panel de administración; elijo y conecto cada pieza yo mismo. |
| Pydantic en modo estricto | Rechaza un monto con decimales o un texto en vez de convertirlo en silencio. Sus patrones se validan contra el texto completo. | Valida la forma de los datos, no las reglas de negocio; esas viven en `domain/`. |
| PostgreSQL | Transacciones ACID, bloqueo de filas (`FOR UPDATE` para la bolsa y `FOR NO KEY UPDATE` para las cuentas), restricciones `CHECK` y `UNIQUE`, índices únicos parciales y llaves foráneas. | Necesita un servidor (lo resuelve Docker) y un bloqueo mal ordenado o mal elegido causa deadlocks. |
| SQLAlchemy 2 y Alembic | Dan control fino de transacciones y bloqueos (`with_for_update(key_share=True)`), y migraciones versionadas y reproducibles. | Su mapa de identidad puede devolver un objeto viejo aunque la fila esté bloqueada: toda lectura con bloqueo usa `populate_existing`. Tienen curva de aprendizaje. |
| pytest y Hypothesis | pytest es el estándar. Hypothesis genera casos que no se me ocurrirían, como probar que la suma de las partes siempre es igual al total. | La concurrencia no es determinista; la pruebo con pruebas secuenciales que fijan el orden y con hilos contra una base real. |
| scrypt, `secrets` y `hmac` | Vienen con Python: scrypt hace caro adivinar contraseñas si alguien roba la base, `secrets` genera tokens impredecibles y `hmac.compare_digest` compara sin filtrar información por el tiempo. | No soy experto en seguridad; sigo los parámetros que recomienda OWASP y lo declaro. |
| Docker Compose | Quien evalúa corre todo con un comando, sin instalar nada. | Si Docker falla en su máquina, no arranca; dejo instrucciones alternativas. |
| Angular y TypeScript | HabiCapital usa JavaScript o TypeScript en el frontend, y Angular es el framework que domino, así que puedo explicar cada línea. | Tiene más estructura inicial que otras opciones. Solo muestra datos; nunca calcula dinero. |
| GitHub Actions | Corre las pruebas en cada push y deja una insignia visible como evidencia. | No agrega funcionalidad. |

## 4. Alternativas que descarté

Estas opciones son válidas en otros contextos. Las descarto por este reto concreto, y así lo explico si me preguntan.

| Alternativa | Por qué no la uso |
| --- | --- |
| Django | Es completo pero pesado. Su ORM y su panel esconden justo lo que quiero controlar y me costaría más tiempo. |
| Flask | Sirve, pero no trae validación ni documentación; las reconstruiría a mano. |
| Spring Boot (Java) | Lo estoy aprendiendo y es robusto, pero lo domino menos que Python y escribo más lento con él. |
| Node con TypeScript | Es una buena opción, pero HabiCapital usa Python en el backend y cambiar de lenguaje no me aporta nada en 72 horas. |
| React con Vite | Era el plan inicial, pero conozco Angular y no React; no podría defender el código en la entrevista. |
| MongoDB u otra base no relacional | Da menos garantías declarativas (restricciones y llaves foráneas), y la partida doble es un modelo naturalmente relacional. |
| SQLite | Es simple, pero no reproduce la concurrencia real de producción. PostgreSQL sí. |
| Celery, Redis o colas de mensajes | Agregan infraestructura para algo que resuelve un hilo dentro del proceso, cada 60 segundos. |
| Aislamiento `SERIALIZABLE` | Obligaría a reintentar muchas transacciones; con `READ COMMITTED` y bloqueos explícitos controlo exactamente qué se serializa. |
| Microservicios | HabiCapital describe una arquitectura distribuida, pero en 72 horas un monolito modular con capas claras es más seguro de probar. |
| Terraform (infraestructura como código) | HabiCapital lo menciona, pero no aporta a la pregunta del reto. Lo declaro como fuera de alcance. |

## 5. Qué debo investigar y dónde

Primero lo que protege el dinero, después los frameworks. Las fuentes son los sitios oficiales de cada herramienta. Confirma que la guía corresponda a la versión que instales.

| Tema | Qué necesito saber | Dónde buscar | Cuándo |
| --- | --- | --- | --- |
| Bloqueos en PostgreSQL | Niveles de aislamiento, `FOR UPDATE` contra `FOR NO KEY UPDATE`, por qué las llaves foráneas toman `FOR KEY SHARE`, deadlocks | postgresql.org/docs (control de concurrencia y bloqueo explícito, tabla de conflictos entre bloqueos de fila) | T2 y T6 |
| Restricciones SQL | `CHECK`, `UNIQUE`, índices únicos parciales y llaves foráneas | postgresql.org/docs | T2 |
| Partida doble | Por qué cada transacción suma cero y qué verifican las invariantes | `SPEC.md` (secciones 3.9 y 4) | T3 |
| Idempotencia | Clave del cliente, `INSERT ... ON CONFLICT DO NOTHING RETURNING` y reconstruir la respuesta | docs.stripe.com (solicitudes idempotentes) y postgresql.org/docs (`INSERT`) | T6 |
| SQLAlchemy 2 | Sesiones, transacciones, `with_for_update(key_share=True)`, `populate_existing` y el mapa de identidad | docs.sqlalchemy.org (tutorial unificado y "Populate Existing") | T1 y T6 |
| Máquinas de estados | Estados de la bolsa y del participante | `SPEC.md` (sección 6.4) | T9 |
| FastAPI | Rutas, dependencias, manejo de errores y `lifespan` | fastapi.tiangolo.com (tutorial) | T8 y T14 |
| Pydantic en modo estricto | Tipos estrictos, patrones y campos prohibidos | docs.pydantic.dev | T8 |
| Alembic | Generar y aplicar migraciones | alembic.sqlalchemy.org | T1 y T2 |
| pytest | Fixtures de sesión y de prueba, parametrización | docs.pytest.org | T1 |
| Hypothesis | Estrategias y pruebas de propiedades | hypothesis.readthedocs.io | T9 |
| Pruebas de concurrencia | Hilos con `threading.Barrier` y conexiones separadas | docs.python.org (`threading`, `concurrent.futures`) | T7 |
| Zonas horarias | Fechas con zona obligatoria en la entrada, UTC en la base y `America/Bogota` solo para mostrar | docs.python.org (`zoneinfo`, `datetime`) | T9 |
| Seguridad básica | scrypt con los parámetros de OWASP, `secrets` y `hmac.compare_digest` | owasp.org (Password Storage Cheat Sheet) y docs.python.org | T5 |
| Docker Compose | Servicios, volúmenes y esperas de salud de la base | docs.docker.com/compose | T16 |
| Angular | Servicios, interceptores HTTP y componentes | angular.dev | Solo si hay frontend |
| GitHub Actions | Un flujo que corra las pruebas con PostgreSQL como servicio | docs.github.com/actions | Si sobra tiempo |

## 6. Plan de estudio durante el reto

Ya no hay tiempo para un bloque de estudio previo: estudio cada tema justo antes de la tarea que lo usa (columna "Cuándo" de la sección 5), con la IA como tutora. Para cada tarea sigo el mismo método:

1. Antes de aprobar el plan, leo las secciones del SPEC que la tarea indica (5 a 10 minutos).
2. Al revisar el diff, pido que me explique cada bloque que no entienda.
3. Al terminar, me hago la pregunta de comprensión de la tabla siguiente.

| Momento | Pregunta que debo poder responder |
| --- | --- |
| Fase 2: base de datos | ¿Qué restricción de la base impediría un aporte duplicado aunque mi código fallara? |
| Fase 3: núcleo contable | ¿Por qué dos transferencias simultáneas desde la misma cuenta no la dejan en negativo, y qué hace `populate_existing`? |
| Fases 4 a 7: API, bolsas, cancelación y vencimiento | ¿Qué pasa si alguien aporta mientras el creador cancela, y por qué un retiro deja a los demás por confirmar? |
| Fase 9: entrega | ¿Cómo se cumple ACID en cada operación, y por qué la liquidación se reparte en varias transacciones? |

## 7. Cómo justificarlo en el README

Este borrador va en primera persona, para el punto 1 del README. Reescríbelo al final con lo que realmente hayas hecho.

> Elegí Python y FastAPI porque son el stack de backend que HabiCapital usa en producción y porque son las herramientas que mejor domino para un plazo de 72 horas. Elegí PostgreSQL porque necesito transacciones atómicas, bloqueo de filas y restricciones que impidan saldos negativos o duplicados incluso si mi código falla: la base de datos es mi última defensa. Guardo el dinero en pesos enteros y no en decimales, porque los decimales binarios acumulan errores. Uso SQLAlchemy y Alembic para controlar las transacciones y versionar el esquema, pytest y Hypothesis para probar propiedades (por ejemplo, que la suma de las partes de una bolsa siempre sea igual al total) y Docker Compose para que cualquiera corra el proyecto con un solo comando. Dejé fuera Terraform y los microservicios porque no aportaban a la pregunta del reto y me habrían quitado tiempo de las pruebas del núcleo.

Lo que no sé todavía lo escribo aparte, en el punto 5, con honestidad.

## 8. Preguntas de entrevista sobre el stack

| Pregunta | Idea central de mi respuesta |
| --- | --- |
| ¿Por qué PostgreSQL y no MongoDB? | Necesito transacciones, restricciones y llaves foráneas. La partida doble es un modelo relacional y la base me protege aunque mi código falle. |
| ¿Qué pasa si dos transferencias salen a la vez de la misma cuenta? | Bloqueo la cuenta con `FOR NO KEY UPDATE`, siempre en el mismo orden, leo el saldo después de bloquear y lo actualizo con `saldo = saldo + :delta`. Además, la base tiene `saldo >= 0`. Lo probé con 100 transferencias simultáneas. |
| ¿Por qué `FOR NO KEY UPDATE` y no `FOR UPDATE`? | Las llaves foráneas toman un bloqueo que choca con `FOR UPDATE`, y dos operaciones del mismo usuario se trababan al insertar sus claves. Como el id de una cuenta nunca cambia, el bloqueo más débil protege el saldo igual. |
| ¿Qué es `populate_existing` y por qué lo usas? | SQLAlchemy no refresca un objeto que ya está en la sesión. Sin esa opción, la fila quedaría bloqueada pero yo leería un saldo viejo. Lo encontró una auditoría con otro modelo. |
| ¿Qué pasa si alguien paga mientras el creador cancela la bolsa? | Bloqueo primero la bolsa y reviso su estado después del bloqueo. La operación que llega segunda ve el estado nuevo y se rechaza. |
| ¿Se cumple ACID? | Cada operación de dinero es una sola transacción. La liquidación de una bolsa son varias, una por participante, y la hice segura de repetir porque la deuda sale del libro. |
| ¿Por qué enteros y no `Decimal`? | Los enteros son exactos y simples. `Decimal` sirve si hay centavos, pero obliga a fijar el modo de redondeo. Mi supuesto es COP sin centavos. |
| ¿Por qué FastAPI y no Django? | Me da validación y documentación sin esconder el control de las transacciones. Django es más pesado para lo que necesito. |
| ¿Qué hace la base de datos que no haga tu código? | Es la última defensa: `CHECK`, `UNIQUE`, índices únicos parciales y llaves foráneas impiden estados inválidos aunque haya un bug. |
| ¿Cómo sabes que tus pruebas sirven? | Cada invariante tiene una prueba que introduce una violación y comprueba que la detecta. Si alcanzo, también rompo el código a propósito y veo fallar una prueba. |
| ¿Por qué un hilo y no Celery? | El barrido es una función cada 60 segundos. Una cola agregaría infraestructura sin ganar seguridad, porque el estado en la base ya es la cola. |
| ¿Por qué un monolito y no microservicios? | Con 72 horas, un monolito con capas claras es más seguro de probar. Lo declaro como decisión, no como desconocimiento. |
| ¿Qué cambiarías con millones de usuarios? | Repartir la cuenta de sistema en varias filas, réplicas de lectura, particionar el libro por fecha, verificar invariantes solo sobre lo nuevo y más observabilidad. Aún no domino los detalles y lo digo. |
