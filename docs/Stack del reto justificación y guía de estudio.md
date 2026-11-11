# Stack del reto: justificación y guía de estudio

Uso Python, FastAPI y PostgreSQL porque es el stack que HabiCapital declara en producción, el más sólido para mover dinero con garantías transaccionales y el que mejor entiende la IA que me asiste. Las versiones exactas no están fijadas aquí: confirma la vigente en la documentación oficial de cada herramienta.

## 1. Resumen del stack

| Capa | Herramienta | Para qué la uso | Estudio |
| --- | --- | --- | --- |
| Lenguaje | Python 3 | Toda la lógica del backend | Ya lo uso |
| API web | FastAPI | Endpoints, validación y documentación interactiva | Alto |
| Validación | Pydantic (modo estricto) | Rechazar montos inválidos en la entrada | Alto |
| Base de datos | PostgreSQL | Libro contable, transacciones y restricciones | Alto |
| Acceso a datos | SQLAlchemy 2 | Modelos, consultas y control de transacciones | Alto |
| Migraciones | Alembic | Versionar el esquema de la base | Medio |
| Pruebas | pytest y Hypothesis | Pruebas normales y de propiedades | Alto |
| Contenedores | Docker y Docker Compose | Correr todo con un comando | Medio |
| IA | API de Claude con tool use | Convertir texto en un borrador de cobro | Medio |
| Frontend | React, TypeScript y Vite | Demo mínima | Bajo |
| Automatización | Makefile y GitHub Actions | Comandos y pruebas en cada push | Bajo |

## 2. Por qué este stack: los criterios

Elegí con seis criterios, en este orden de peso:

1. **Alineación con HabiCapital.** Su documento describe backend en Python, bases de datos relacionales y frontend en JavaScript o TypeScript. Usar lo mismo me acerca a lo que van a revisar y a lo que haría en el cargo.
2. **Garantías para el dinero.** Necesito transacciones atómicas, bloqueo de filas y restricciones en la base de datos. Si mi código falla, la base debe impedir un saldo negativo o un movimiento duplicado.
3. **Qué tan bien me asiste la IA.** Su documento dice que el stack se eligió para que los modelos tengan buena data de entrenamiento. Las herramientas populares generan código más fiable y me dan más ayuda.
4. **Lo que ya sé.** Domino Python, SQL y Git. Java y Spring Boot los conozco menos. Una herramienta que ya uso me deja más tiempo para lo importante.
5. **Tiempo.** Son 72 horas. Prefiero librerías maduras y con poca configuración.
6. **Poder explicarlo.** En la entrevista haré pair programming sobre mi código. Cada pieza debe ser algo que pueda defender.

## 3. Justificación herramienta por herramienta

Cada herramienta tiene una razón y un límite que debo reconocer, porque en la entrevista me preguntarán por ambos.

| Herramienta | Por qué la elijo | Límite que reconozco |
| --- | --- | --- |
| Python | Es el lenguaje de backend de HabiCapital. Sus enteros no se desbordan, ideal para pesos. Tiene un gran ecosistema de pruebas. | Es más lento que un lenguaje compilado, algo irrelevante a esta escala. |
| FastAPI | Valida entradas con Pydantic y genera documentación interactiva que me sirve para la demo. Su tipado explícito ayuda a la IA y a mí. | No trae ORM ni panel de administración; elijo y conecto cada pieza yo mismo. |
| Pydantic en modo estricto | Rechaza un monto con decimales o un texto en vez de convertirlo en silencio. | Valida la forma de los datos, no las reglas de negocio; esas viven en el dominio. |
| PostgreSQL | Transacciones ACID, bloqueo con `SELECT ... FOR UPDATE`, restricciones `CHECK` y `UNIQUE`, y tipos numéricos exactos. | Necesita un servidor (lo resuelve Docker) y un bloqueo mal ordenado causa deadlocks. |
| SQLAlchemy 2 y Alembic | Dan control fino de transacciones y bloqueos, y migraciones versionadas y reproducibles. | Tienen curva de aprendizaje; en las partes críticas puedo escribir SQL directo. |
| pytest y Hypothesis | pytest es el estándar. Hypothesis genera casos que no se me ocurrirían, como probar que la suma de las partes siempre es igual al total. | La concurrencia es más difícil de probar; la pruebo con hilos contra una base real. |
| Docker Compose | Quien evalúa corre todo con un comando, sin instalar nada. | Si Docker falla en su máquina, no arranca; dejo instrucciones alternativas. |
| API de Claude con tool use | Devuelve un borrador con esquema JSON fijo, y un modelo pequeño alcanza y es barato. | Puede equivocarse. Por eso solo propone: el código valida y el usuario confirma. Necesita llave y red. |
| React, TypeScript y Vite | HabiCapital usa JavaScript o TypeScript en el frontend. TypeScript atrapa errores de tipo. | Solo muestra datos; nunca calcula dinero. |
| GitHub Actions | Corre las pruebas en cada push y deja una insignia visible como evidencia. | No agrega funcionalidad. |

## 4. Alternativas que descarté

Estas opciones son válidas en otros contextos. Las descarto por este reto concreto, y así lo explico si me preguntan.

| Alternativa | Por qué no la uso |
| --- | --- |
| Django | Es completo pero pesado. Su ORM y su panel esconden justo lo que quiero controlar y me costaría más tiempo. |
| Flask | Sirve, pero no trae validación ni documentación; las reconstruiría a mano. |
| Spring Boot (Java) | Lo estoy aprendiendo y es robusto, pero lo domino menos que Python y escribo más lento con él. |
| Node con TypeScript | Es una buena opción, pero HabiCapital usa Python en el backend y cambiar de lenguaje no me aporta nada en 72 horas. |
| MongoDB u otra base no relacional | Da menos garantías declarativas (restricciones y llaves foráneas), y la partida doble es un modelo naturalmente relacional. |
| SQLite | Es simple, pero no reproduce la concurrencia real de producción. PostgreSQL sí. |
| Celery, Redis o colas de mensajes | Agregan infraestructura para algo que resuelve una función llamada por un programador de tareas. |
| Microservicios | HabiCapital describe una arquitectura distribuida, pero en 72 horas un monolito modular con capas claras es más seguro de probar. |
| Terraform (infraestructura como código) | HabiCapital lo menciona, pero no aporta a la pregunta del reto. Lo declaro como fuera de alcance. |

## 5. Qué debo investigar y dónde

Primero lo que protege el dinero, después los frameworks. Las fuentes son los sitios oficiales de cada herramienta (busca el dominio y entra por su tutorial). No los abrí al escribir esto, así que confirma que la guía corresponda a la versión que instales.

| Tema | Qué necesito saber | Dónde buscar | Cuándo |
| --- | --- | --- | --- |
| Transacciones y bloqueos en PostgreSQL | BEGIN y COMMIT, niveles de aislamiento, `SELECT ... FOR UPDATE`, deadlocks | postgresql.org/docs (control de concurrencia y bloqueo explícito) | Antes de programar |
| Restricciones SQL | `CHECK`, `UNIQUE`, llaves foráneas e índices | postgresql.org/docs | Antes de programar |
| Partida doble | Qué es un libro contable y por qué cada transacción suma cero | Busca "double-entry ledger design" y pide a la IA ejemplos con números | Antes de programar |
| Dinero con enteros | Por qué no usar float, redondeo y el método del resto mayor | docs.python.org (módulo `decimal` y "Floating Point Arithmetic: Issues and Limitations") | Antes de programar |
| Idempotencia | Qué es una clave de idempotencia y cómo evita cobros duplicados | docs.stripe.com (solicitudes idempotentes) como ejemplo del concepto | Antes de programar |
| FastAPI | Rutas, dependencias, manejo de errores y su integración con Pydantic | fastapi.tiangolo.com (tutorial) | Mientras construyo |
| Pydantic en modo estricto | Tipos estrictos, validadores y esquemas de entrada y salida | docs.pydantic.dev | Mientras construyo |
| SQLAlchemy 2 | Sesiones, transacciones y `with_for_update` | docs.sqlalchemy.org (tutorial unificado) | Mientras construyo |
| Alembic | Generar y aplicar migraciones | alembic.sqlalchemy.org | Mientras construyo |
| pytest | Fixtures, parametrización y pruebas con base de datos | docs.pytest.org | Mientras construyo |
| Hypothesis | Estrategias y pruebas de propiedades | hypothesis.readthedocs.io | Mientras construyo |
| Pruebas de concurrencia | Hilos con conexiones separadas para simular transferencias simultáneas | docs.python.org (`concurrent.futures`) | Mientras construyo |
| Zonas horarias | UTC y `America/Bogota` con `zoneinfo` | docs.python.org | Mientras construyo |
| Docker Compose | Servicios, volúmenes y esperas de salud de la base | docs.docker.com/compose | Mientras construyo |
| Seguridad básica | No subir llaves al repo y guardar contraseñas con hash | owasp.org | Mientras construyo |
| API de Claude: tool use | Definir un esquema de salida y validarlo | docs.claude.com | Si sobra tiempo |
| React, TypeScript y Vite | Componentes, estado y peticiones a la API | react.dev, vite.dev, typescriptlang.org | Si sobra tiempo |
| GitHub Actions | Un flujo que corra las pruebas en cada push | docs.github.com/actions | Si sobra tiempo |

## 6. Plan de estudio antes y durante el reto

Dedico unas 3 horas antes de escribir código a lo que protege el dinero, y aprendo el resto construyendo, con la IA como tutora. Para cada tema sigo el mismo método: leo lo mínimo, pruebo en pequeño, pido que me haga preguntas de comprensión y anoto lo aprendido en `DECISIONS.md`.

| Momento | Qué estudio o hago | Tiempo | Cómo sé que lo entendí |
| --- | --- | --- | --- |
| Antes de escribir código | Bloqueos y transacciones de PostgreSQL, partida doble e idempotencia. Pruebo `FOR UPDATE` con dos terminales abiertas y escribo la función de división con una prueba de Hypothesis. | 3 horas | Puedo explicar por qué dos transferencias simultáneas no dejan un saldo negativo. |
| Fases 2 y 3: base de datos y núcleo contable | Sesiones y transacciones de SQLAlchemy, fixtures de pytest y la prueba de concurrencia. Pido a la IA que me explique cada bloque que genere. | Mientras construyo | Rompo a propósito el bloqueo y mi prueba de concurrencia falla. |
| Fases 4 a 6: API, grupos y recurrencia | FastAPI, Pydantic estricto y Alembic. Reviso zonas horarias y meses con menos días. | Mientras construyo | Mi API rechaza montos con decimales, negativos y duplicados. |
| Fase 7: IA | Tool use de Claude y la evaluación de 15 a 20 frases. | 1 hora de lectura | Tengo una tabla con cuántas frases interpretó bien. |
| Fase 8: interfaz | Solo lo mínimo de React. La IA la construye y yo reviso que no calcule dinero. | Mientras construyo | Puedo explicar cómo la interfaz llama a la API. |
| Último día | Simulacro de entrevista con cambios sorpresa: comisión, límite diario y reverso de una transferencia. | 2 horas | Hago cada cambio en menos de 20 minutos, con las pruebas en verde. |

## 7. Cómo justificarlo en el README

Este borrador va en primera persona, para el punto 1 del README. Reescríbelo al final con lo que realmente hayas hecho, porque si algo cambia durante el proyecto, el texto debe cambiar también.

> Elegí Python y FastAPI porque son el stack de backend que HabiCapital usa en producción y porque son las herramientas que mejor domino para un plazo de 72 horas. Elegí PostgreSQL porque necesito transacciones atómicas, bloqueo de filas y restricciones que impidan saldos negativos o duplicados incluso si mi código falla: la base de datos es mi última defensa. Guardo el dinero en pesos enteros y no en decimales, porque los decimales binarios acumulan errores. Uso SQLAlchemy y Alembic para controlar las transacciones y versionar el esquema, pytest y Hypothesis para probar propiedades (por ejemplo, que la suma de las partes de un cobro siempre sea igual al total) y Docker Compose para que cualquiera corra el proyecto con un solo comando. Dejé fuera Terraform y los microservicios porque no aportaban a la pregunta del reto y me habrían quitado tiempo de las pruebas del núcleo.

Lo que no sé todavía lo escribo aparte, en el punto 5, con honestidad.

## 8. Preguntas de entrevista sobre el stack

Estas son las preguntas que más probablemente harán sobre mis decisiones, con la idea central de cada respuesta. Las digo con mis palabras y, si no sé algo, lo reconozco.

| Pregunta | Idea central de mi respuesta |
| --- | --- |
| ¿Por qué PostgreSQL y no MongoDB? | Necesito transacciones, restricciones y llaves foráneas. La partida doble es un modelo relacional y la base me protege aunque mi código falle. |
| ¿Qué pasa si dos transferencias salen a la vez de la misma cuenta? | Bloqueo las filas con `FOR UPDATE` siempre en el mismo orden y la base tiene una restricción de saldo mayor o igual a cero. Lo probé con 100 transferencias simultáneas. |
| ¿Por qué enteros y no `Decimal`? | Los enteros son exactos y simples. `Decimal` sirve si hay centavos, pero obliga a fijar el modo de redondeo. Mi supuesto es COP sin centavos. |
| ¿Por qué FastAPI y no Django? | Me da validación y documentación sin esconder el control de las transacciones. Django es más pesado para lo que necesito. |
| ¿Qué hace la base de datos que no haga tu código? | Es la última defensa: `CHECK`, `UNIQUE` y llaves foráneas impiden estados inválidos aunque haya un bug. |
| ¿Cómo sabes que tus pruebas sirven? | Rompo el código a propósito, por ejemplo quito el bloqueo, y compruebo que una prueba falla. |
| ¿Qué pasa si falla el modelo de IA? | La app sigue funcionando con el formulario normal. La IA solo propone y nunca toca el libro contable. |
| ¿Por qué un monolito y no microservicios? | Con 72 horas, un monolito con capas claras es más seguro de probar. Lo declaro como decisión, no como desconocimiento. |
| ¿Qué cambiarías con millones de usuarios? | Réplicas de lectura, particionar el libro por fecha, colas para trabajos en segundo plano y más observabilidad. Aún no domino los detalles y lo digo. |
