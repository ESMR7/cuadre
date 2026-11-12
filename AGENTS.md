# Cuadre: instrucciones para agentes de código

Cuadre es una billetera digital simulada (reto técnico de HabiCapital): cuentas, carga de saldo, transferencias, saldo, historial y **bolsas**: cobros en grupo con una cuenta común, división exacta y transferencia final a una cuenta objetivo. Es dinero: el sistema no puede perder ni crear un peso.

## Contexto

- **Fuente de verdad del producto:** `SPEC.md`. Plan general y guías: `docs/`. Si este archivo y `SPEC.md` se contradicen, detente y pregunta.
- **Fuera de alcance:** lo que `SPEC.md` (sección 11) declara fuera de alcance no se implementa ni se propone sin que el usuario lo pida.
- **Stack:** Python 3.12+, FastAPI (endpoints síncronos `def`), SQLAlchemy 2 síncrono con psycopg 3, Pydantic v2 en modo estricto, Alembic, PostgreSQL 17 en Docker, pytest, Hypothesis, httpx y Ruff. Más adelante: React, TypeScript y Vite.
- **Barrido de vencidas:** hilo iniciado en el `lifespan` de FastAPI, cada 60 s (variable de entorno), con un solo worker de uvicorn. Usa su propia sesión, una transacción por paso y captura excepciones por bolsa y por ciclo. Solo la API y este hilo leen el reloj.
- **Estructura:**

```
backend/app/api/        endpoints delgados: validan y delegan
backend/app/services/   casos de uso: libro contable, bolsas y vencimientos
backend/app/domain/     reglas puras sin base de datos: división, estados de la bolsa, validaciones
backend/app/db/         modelos, sesión y migraciones
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
3. Partida doble: todo lo que mueve valor es una transacción con una cuenta de origen y una de destino distintas y un monto positivo, con exactamente dos movimientos: −monto en el origen y +monto en el destino. Nada aparece ni desaparece: todo sale de una cuenta y llega a otra. Cargar saldo sale de la cuenta de sistema. El servicio del libro verifica la suma cero antes de confirmar.
4. Cada operación de dinero es una sola transacción de base de datos: todo o nada.
5. Los movimientos son inmutables: nada de `UPDATE` ni `DELETE`. Un error se corrige con un movimiento compensatorio.
6. Concurrencia: un solo orden dentro de toda operación: (1) leer la sesión sin bloquearla; (2) registrar la clave de idempotencia con `INSERT ... ON CONFLICT`; (3) bloquear la fila de la bolsa con `SELECT ... FOR UPDATE`, si la operación toca una; (4) bloquear las cuentas por id ascendente con `SELECT ... FOR NO KEY UPDATE`, incluida la de quien paga. Las cuentas usan `FOR NO KEY UPDATE` y no `FOR UPDATE` porque su id nunca cambia, y así no chocan con el `FOR KEY SHARE` que toman las llaves foráneas al insertar claves, transacciones o bolsas que las referencian. Dentro de una bolsa, el estado se revisa antes que el plazo. Los ids de cuenta son texto ASCII con `COLLATE "C"`, así que el orden es el mismo en PostgreSQL y en Python. Nunca se bloquean dos bolsas en una misma transacción: el barrido procesa cada bolsa en su propia transacción. El estado de la bolsa se lee después de bloquearla y decide si la operación sigue. Aislamiento `READ COMMITTED`. Reintentos acotados (máximo 3) del caso de uso completo, solo ante los errores `40P01` y `40001`; si se agotan, 503. Prohibido usar bloqueos en memoria (`threading.Lock`, `asyncio.Lock`) o estado global para saldos.
7. Idempotencia: toda operación de usuario que puede mover dinero (`cargar`, `transferir`, `aportar` y `retirarse`) recibe una clave generada por el cliente (cabecera `Idempotency-Key`, UUID v4), con `UNIQUE (cuenta_solicitante_id, clave)`, donde la cuenta solicitante es la cuenta personal de quien hace la petición (no el origen de la transacción). La clave identifica la intención y no depende de la sesión ni del token. La clave siempre se guarda si la operación confirma; la transacción solo existe si se movió dinero. Las operaciones del sistema (devoluciones del barrido y transferencia final) no llevan clave: las protegen la deuda recalculada y los índices únicos parciales. Se guarda junto con el hash SHA-256 de la operación, los ids de la ruta y el cuerpo canónico. Misma clave y mismo hash: se devuelve el resultado original, reconstruido desde el libro, sin mover dinero otra vez. Misma clave con otro hash: 409 `clave_reutilizada`. La clave solo persiste si la transacción confirma. La verificación es un `INSERT ... ON CONFLICT`, nunca un `SELECT` seguido de un `INSERT`.
8. La base de datos también defiende, sin triggers: `CHECK (monto > 0)` en `transacciones` y `CHECK (monto <> 0)` en `movimientos`; `UNIQUE` para la idempotencia; índices únicos parciales para un solo aporte y una sola devolución por participante y bolsa, y una sola transferencia final por bolsa (cierre único); y restricciones de saldo por tipo de cuenta: `CHECK (saldo >= 0)` en toda cuenta salvo la única de tipo `sistema`, que cumple `CHECK (saldo <= 0)`. Esa es la única excepción y no se amplía a ninguna otra cuenta. Nunca elimines ni relajes una restricción para que algo funcione.
9. La división es exacta y determinista: la suma de las partes siempre es igual al total. Usa las funciones de `domain/`. El sobrante de la división lo paga el creador, que siempre es participante (`SPEC.md`, sección 3.7).
10. Tiempo: guarda en UTC e interpreta las fechas límite en `America/Bogota`. Toda función que dependa de la hora recibe `ahora` como parámetro. Solo la API y el hilo del barrido leen el reloj. Un token o una bolsa están vigentes mientras `ahora` es estrictamente menor que su fecha de expiración.
11. Rechaza entradas inválidas: montos no enteros, cero, negativos o por encima del tope definido en `SPEC.md`, cuentas inexistentes, transferencias a uno mismo y pagos distintos a la parte exacta. Nunca redondees en silencio.
12. Códigos HTTP: **422** si la petición es inválida por sí sola, sin importar el estado de ningún recurso (forma, monto cero, negativo o sobre el tope, transferencia a uno mismo). **409** si la petición es válida pero choca con el estado actual de un recurso o con una regla que depende de ese estado (saldo insuficiente, fuera de plazo, bolsa cerrada, ya pagó, clave reutilizada). Las dos categorías no se mezclan. Además: 400 sin `Idempotency-Key`, 401 sin sesión válida, 403 sin permiso sobre la bolsa, 404 si no existe y 503 con reintentos agotados. Todo error sale como `{"codigo": "...", "mensaje": "..."}`.

Si una tarea exige romper alguna de estas reglas, detente y pregunta.

## Reglas de las bolsas

1. Cada bolsa tiene su propia cuenta de tipo `bolsa`. Solo admite aportes, devoluciones y la transferencia final a la cuenta objetivo; ninguna otra operación la toca.
2. La configuración se fija al crear la bolsa y no cambia: la parte de cada participante, la cuenta objetivo, la fecha límite y la política de vencimiento (bandera `transferir_al_vencer`: verdadero envía lo de quienes están en `pagado`, falso devuelve todo). Cada bolsa es de un solo uso. Estados de la bolsa: `abierta`, `cancelada`, `liquidando` y `cerrada`. Estados del participante: `pendiente`, `pagado`, `por_confirmar` y `retirado`.
3. Solo pagos completos: cada participante paga exactamente su parte.
4. Un participante puede retirarse mientras la bolsa esté `abierta` o `cancelada` y antes de la fecha límite, haya pagado o no. Si pagó, se le devuelve su aporte en la misma transacción. La meta baja en su parte, y todos los participantes en `pagado` pasan a `por_confirmar`: deben aceptar los términos nuevos con `confirmar`, que no mueve dinero. Un retiro nunca completa la bolsa.
5. Cuando todos los participantes activos (los que no están `retirado`) están en `pagado`, el saldo de la bolsa se transfiere a la cuenta objetivo en la misma transacción del aporte o la confirmación que lo logró. Si se retiran todos, la bolsa se cierra sin mover dinero.
6. Nada se envía sin consentimiento. Al vencer, quien no está en `pagado` pasa a `retirado` y se le devuelve lo suyo. Con `transferir_al_vencer` verdadero se envía lo de quienes siguen en `pagado`; con falso se devuelve todo. Las devoluciones se hacen en una transacción por participante. Solo el barrido liquida: una petición que encuentra la bolsa vencida la rechaza con 409 `fuera_de_plazo` y no mueve dinero.
7. Solo el creador cancela, aunque se haya retirado, mientras la bolsa esté `abierta` y antes de la fecha límite. Cancelar no mueve dinero. Con política de devolver, todos pasan a `retirado` y el barrido devuelve. Con política de transferir, los pendientes pasan a `retirado`, los que pagaron a `por_confirmar` y la bolsa a `cancelada`: cada uno confirma o se retira hasta la fecha límite, y al vencer se aplica la regla 6.
8. Lo que se le debe devolver a cada participante se calcula desde los movimientos del libro (aportes menos devoluciones), nunca desde un contador aparte. Por eso una devolución repetida o retomada tras una falla no puede pagar de más.
9. Una bolsa cerrada siempre tiene saldo cero. El único estado con saldo pendiente de devolver y sin operaciones de usuario es `liquidando` (`SPEC.md`, sección 7).

## Protocolo de trabajo (obligatorio en cada tarea)

Palabras clave del usuario: `PLAN:`, `CAMBIOS:`, `APROBADO`, `SIGUE` y `AUDITA:`.

### Fase 1. Plan (sin tocar archivos)

Al recibir una tarea, lee `SPEC.md` y los archivos relevantes. No crees, edites ni borres archivos, y no ejecutes comandos que cambien algo. Responde con este formato:

1. **Objetivo:** una o dos frases.
2. **Archivos** a crear o modificar.
3. **Diseño:** funciones y firmas, flujo y cambios de esquema.
4. **Reglas del dinero y de las bolsas afectadas**, y cómo se cumplen.
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
- Revisa tu propio diff contra las reglas del dinero y de las bolsas, una por una.

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

Solo lectura. Revisa el alcance indicado contra las reglas del dinero y de las bolsas: concurrencia, redondeo, idempotencia, atomicidad, validaciones y pruebas débiles. Si el alcance es "último cambio", usa `git diff`. Entrega los hallazgos ordenados por gravedad (alta, media, baja), con archivo y línea, y la prueba que detectaría cada problema. No corrijas nada sin un plan aprobado.

## Convenciones de código

- Respuestas, comentarios, docstrings y mensajes de commit en español.
- Identificadores en español, sin tildes ni ñ (`transferir`, `cuenta_origen`), salvo términos técnicos estándar.
- Simple y explícito antes que ingenioso. Funciones pequeñas y con tipos. Sin abstracciones especulativas.
- Endpoints delgados: la lógica vive en `services/` y `domain/`.
- Fronteras de capas: `domain/` no importa `sqlalchemy` ni `fastapi`; `services/` no importa `fastapi`. Una prueba lo verifica.
- Errores de dominio como excepciones propias; la API las traduce a códigos HTTP (400, 401, 403, 404, 409, 422, 503) según la regla 12 del dinero. Los ids de bolsa son UUID.
- Una sesión de base de datos por petición. Nunca compartas sesiones entre hilos. La API no hace `commit`: el servicio es dueño de la transacción.

## Pruebas

- Usa la base `cuadre_test` (variable `TEST_DATABASE_URL`). Nunca la de desarrollo. Un fixture de sesión la crea de cero con `alembic upgrade head` al empezar y la borra al terminar, y se niega a tocar una base cuyo nombre no termine en `_test` (`SPEC.md`, sección 10.2).
- Cada prueba es independiente y crea sus propios datos. Después de cada prueba se corren las invariantes, se vacían las tablas con `TRUNCATE` y se vuelve a crear la cuenta de sistema.
- `TRUNCATE`, `UPDATE` y `DELETE` sobre el libro solo se permiten en esos fixtures y en las pruebas de las invariantes. Nunca en el código de la aplicación.
- Lo que mueve dinero se prueba contra PostgreSQL real, sin simulaciones de la base.
- Hypothesis para las propiedades de `domain/`, como que la suma de las partes sea igual al total.
- Concurrencia: hilos con conexiones separadas que arrancan juntos con una barrera. La prueba acepta cualquiera de los resultados permitidos por la tabla 8.4 de `SPEC.md`, verifica las reglas que valen en cualquier orden y termina corriendo las invariantes. Los choques de bolsas se repiten 10 veces con datos nuevos. Casos mínimos de bolsas: último aporte contra retiro, contra cancelación y contra vencimiento; última confirmación contra retiro; y dos aportes finales al mismo tiempo. La transferencia final ocurre una sola vez.
- Hora fija inyectada: nada de `datetime.now()` dentro de la lógica que se prueba.
- Barrido: se prueba llamando a `procesar_vencidas(ahora)` con hora fija. El hilo se apaga en las pruebas con la variable de entorno. Procesar dos veces no duplica movimientos y una bolsa fallida no detiene a las demás.
- Idempotencia: dos hilos con la misma clave y el mismo cuerpo producen un solo conjunto de movimientos y la misma respuesta; la misma clave con otro cuerpo da 409.
- Una prueba verifica las fronteras de importación de `domain/` y `services/`.
- Cada restricción de la base tiene al menos una prueba que intenta violarla y comprueba que PostgreSQL la rechaza.
- Toda prueba que toca la base termina corriendo todas las invariantes de `SPEC.md` (sección 4). Si alguna falla, la prueba falla.
- Cada invariante tiene una prueba que introduce una violación por SQL directo y comprueba que la consulta la detecta (`SPEC.md`, sección 10.5).
- El hilo del barrido tiene una prueba de humo con un intervalo de 1 s (`SPEC.md`, sección 10.7).
- Nombres: `test_<comportamiento_esperado>`.

## Seguridad y límites

- Nunca leas, muestres ni modifiques `.env`. Usa `.env.example` como referencia y no escribas llaves en el código.
- Contraseñas y tokens de sesión se guardan solo como hash, nunca en claro. No los escribas en logs, respuestas de error ni pruebas impresas.
- La cédula es un dato personal: nunca en logs, respuestas de error ni datos de ejemplo reales.
- `README.md` y `AI_LOG.md` los escribe el autor en primera persona. Solo edita la sección técnica de cómo correr el proyecto, y solo si te lo piden.
- Pide permiso antes de cualquier acción destructiva: `docker compose down -v`, `rm -rf`, `DROP`, borrar archivos o reescribir el historial de git. La única excepción es el fixture que crea, vacía y borra `cuadre_test` durante las pruebas.

## Definición de hecho

Plan aprobado, pruebas escritas antes del código, suite en verde, Ruff limpio, invariantes en verde, reporte entregado y un cambio que el usuario entiende y puede explicar.
