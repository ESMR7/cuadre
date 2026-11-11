# Cuadre: instrucciones para agentes de código

Cuadre es una billetera digital simulada (reto técnico de HabiCapital): cuentas, carga de saldo, transferencias, saldo, historial y cobros divididos en grupos con recurrencia. Es dinero: el sistema no puede perder ni crear un peso.

## Contexto

- **Fuente de verdad del producto:** `SPEC.md`. Plan general y guías: `docs/`. Si este archivo y `SPEC.md` se contradicen, detente y pregunta.
- **Stack:** Python 3.12+, FastAPI (endpoints síncronos `def`), SQLAlchemy 2 síncrono con psycopg 3, Pydantic v2 en modo estricto, Alembic, PostgreSQL 17 en Docker, pytest, Hypothesis, httpx y Ruff. Más adelante: React, TypeScript y Vite.
- **Estructura:**

```
backend/app/api/        endpoints delgados: validan y delegan
backend/app/services/   casos de uso: libro contable, cobros, recurrencia
backend/app/domain/     reglas puras sin base de datos: división, validaciones
backend/app/db/         modelos, sesión y migraciones
backend/app/ai/         parser de cobros (real y falso)
backend/tests/          pruebas
```

- **Comandos** (desde `backend/`, con el entorno virtual activo, salvo Docker):
  - `docker compose up -d db` (desde la raíz)
  - `pytest` (todo) o `pytest -q tests/<ruta>` (una parte)
  - `ruff check .` y `ruff format .`
  - `alembic upgrade head` y `alembic revision --autogenerate -m "<mensaje>"`
  - `uvicorn app.main:app --reload`
  - `make check` (verificación de invariantes, cuando exista)

## Reglas del dinero (no negociables)

1. Los montos son `int` en pesos colombianos. Nunca `float`, en ningún lugar: código, pruebas, JSON ni base de datos (`BIGINT`).
2. Todo movimiento de dinero pasa por el servicio de libro contable. Ningún otro módulo inserta movimientos ni cambia saldos.
3. Partida doble: cada transacción genera movimientos que suman cero. Cargar saldo sale de una cuenta de sistema.
4. Cada operación de dinero es una sola transacción de base de datos: todo o nada.
5. Los movimientos son inmutables: nada de `UPDATE` ni `DELETE`. Un error se corrige con un movimiento compensatorio.
6. Concurrencia: bloquea las cuentas con `SELECT ... FOR UPDATE`, siempre ordenadas por id ascendente. Aislamiento `READ COMMITTED`. Reintentos acotados (máximo 3) solo ante los errores `40P01` y `40001`. Prohibido usar bloqueos en memoria (`threading.Lock`, `asyncio.Lock`) o estado global para saldos.
7. Idempotencia: toda operación que mueve dinero recibe una clave con restricción `UNIQUE`. Un reintento devuelve el resultado original sin mover dinero otra vez.
8. La base de datos también defiende: `CHECK (monto > 0)`, `CHECK (saldo >= 0)`, `UNIQUE` para idempotencia y para `(plantilla_id, periodo)`. Nunca elimines ni relajes una restricción para que algo funcione.
9. La división de un cobro es exacta y determinista: la suma de las partes siempre es igual al total. Usa las funciones de `domain/` y la regla del sobrante definida en `SPEC.md`.
10. Tiempo: guarda en UTC y calcula la recurrencia en `America/Bogota`. Toda función que dependa de la hora recibe `ahora` como parámetro.
11. La IA (`app/ai/`) solo produce borradores. Nunca llama al libro contable ni crea un cobro sin confirmación del usuario.
12. Rechaza entradas inválidas: montos no enteros, cero o negativos, cuentas inexistentes y transferencias a uno mismo. Nunca redondees en silencio.

Si una tarea exige romper alguna de estas reglas, detente y pregunta.

## Protocolo de trabajo (obligatorio en cada tarea)

Palabras clave del usuario: `PLAN:`, `CAMBIOS:`, `APROBADO`, `SIGUE` y `AUDITA:`.

### Fase 1. Plan (sin tocar archivos)

Al recibir una tarea, lee `SPEC.md` y los archivos relevantes. No crees, edites ni borres archivos, y no ejecutes comandos que cambien algo. Responde con este formato:

1. **Objetivo:** una o dos frases.
2. **Archivos** a crear o modificar.
3. **Diseño:** funciones y firmas, flujo y cambios de esquema.
4. **Reglas del dinero afectadas** y cómo se cumplen.
5. **Pruebas a escribir:** nombre y qué verifica cada una (caso normal, borde y error; propiedades o concurrencia cuando aplique).
6. **Supuestos y riesgos.**
7. **Fuera de alcance.**
8. **Preguntas**, si las hay.

Termina con "¿Apruebas el plan?" y detente. No sigas sin `APROBADO`. Ante `CAMBIOS:`, entrega un plan revisado.

### Fase 2. Pruebas primero

Tras `APROBADO`, escribe solo las pruebas y fixtures del plan. Si hace falta, crea firmas vacías que lancen `NotImplementedError` para que las pruebas fallen por la razón correcta y no por errores de importación o sintaxis. Ejecuta las pruebas nuevas y reporta cuáles fallan y por qué. Detente y espera `SIGUE`, salvo que el usuario haya escrito `APROBADO sin pausa`.

### Fase 3. Implementación

Tras `SIGUE`, escribe el código mínimo y claro para que pasen las pruebas. Ejecuta la suite completa después de cada cambio relevante y repite hasta que todo esté en verde.

Prohibido:
- Modificar, borrar, saltar (`skip`, `xfail`) o debilitar pruebas aprobadas para que pasen.
- Simular la base de datos en pruebas que mueven dinero.
- Agregar dependencias, refactorizar o tocar archivos fuera del plan.

Si una prueba aprobada parece incorrecta, o el plan necesita cambiar, detente, explica y pide aprobación. Si tras tres intentos no avanzas, detente y reporta el bloqueo con tus hipótesis.

### Fase 4. Verificación

- `pytest` completo en verde.
- `ruff check .` y `ruff format --check .` sin errores.
- `make check` en verde, si existe.
- Revisa tu propio diff contra las reglas del dinero, una por una.

### Fase 5. Reporte

Entrega:
- Qué hiciste y qué archivos tocaste.
- Resultado de pruebas (pasaron / total) y de Ruff.
- Desviaciones del plan.
- Explicación breve de la parte no obvia, para que el usuario pueda defenderla en una entrevista.
- Propuesta de entrada para `DECISIONS.md`, si hubo una decisión.
- Errores, dudas o correcciones tuyas durante la tarea, para que el usuario decida si van en `AI_LOG.md`.
- Mensaje de commit sugerido.

No hagas `git commit`, `git push` ni cambies de rama salvo que el usuario lo pida.

### Auditoría (`AUDITA: <alcance>`)

Solo lectura. Revisa el alcance indicado contra las reglas del dinero: concurrencia, redondeo, idempotencia, atomicidad, validaciones y pruebas débiles. Si el alcance es "último cambio", usa `git diff`. Entrega los hallazgos ordenados por gravedad (alta, media, baja), con archivo y línea, y la prueba que detectaría cada problema. No corrijas nada sin un plan aprobado.

## Convenciones de código

- Respuestas, comentarios, docstrings y mensajes de commit en español.
- Identificadores en español, sin tildes ni ñ (`transferir`, `cuenta_origen`), salvo términos técnicos estándar.
- Simple y explícito antes que ingenioso. Funciones pequeñas y con tipos. Sin abstracciones especulativas.
- Endpoints delgados: la lógica vive en `services/` y `domain/`.
- Errores de dominio como excepciones propias; la API las traduce a códigos HTTP (400, 404, 409, 422).
- Una sesión de base de datos por petición. Nunca compartas sesiones entre hilos.

## Pruebas

- Usa la base `cuadre_test` (variable `TEST_DATABASE_URL`). Nunca la de desarrollo.
- Cada prueba es independiente y limpia su estado.
- Lo que mueve dinero se prueba contra PostgreSQL real, sin simulaciones de la base.
- Hypothesis para las propiedades de `domain/`, como que la suma de las partes sea igual al total.
- Concurrencia: hilos con conexiones separadas y verificación de invariantes al final.
- Sin red: las pruebas usan el parser de IA falso.
- Hora fija inyectada: nada de `datetime.now()` dentro de la lógica que se prueba.
- Nombres: `test_<comportamiento_esperado>`.

## Seguridad y límites

- Nunca leas, muestres ni modifiques `.env`. Usa `.env.example` como referencia y no escribas llaves en el código.
- `README.md` y `AI_LOG.md` los escribe el autor en primera persona. Solo edita la sección técnica de cómo correr el proyecto, y solo si te lo piden.
- Pide permiso antes de cualquier acción destructiva: `docker compose down -v`, `rm -rf`, `DROP`, borrar archivos o reescribir el historial de git.

## Definición de hecho

Plan aprobado, pruebas escritas antes del código, suite en verde, Ruff limpio, invariantes en verde, reporte entregado y un cambio que el usuario entiende y puede explicar.
