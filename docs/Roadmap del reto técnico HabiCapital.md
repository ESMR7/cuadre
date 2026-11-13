# Roadmap del reto técnico HabiCapital

Plan de trabajo de Edy Santiago Martínez Rojas para el reto. Stack: Python, FastAPI y PostgreSQL; frontend en Angular con TypeScript si alcanza el tiempo. La fuente de verdad del producto es `SPEC.md`: este roadmap solo ordena el trabajo y no redefine reglas.

## 1. Nombre del proyecto

**Cuadre.** Tiene doble sentido: "cuadrar cuentas" entre amigos (el reto habla de la profesora que pierde horas "cuadrando") y el cuadre contable, que es la garantía de que el sistema no pierde un peso. Repo: `cuadre`.

## 2. Alcance

- **Núcleo obligatorio:** crear cuenta, cargar saldo (simulado), transferir, consultar saldo y ver historial.
- **Mi propuesta de valor (una sola cosa): bolsas.** Un cobro en grupo con una cuenta común. La app divide el total de forma exacta, cada participante paga su parte completa o se retira, y cuando todos los activos pagaron y aceptan los términos, el dinero se transfiere solo a la cuenta objetivo.
- **Reglas de producto de las bolsas** (detalle en `SPEC.md`, secciones 6 y 7):
  - Cada bolsa es de un solo uso y su configuración no cambia: partes, cuenta objetivo, fecha límite y política de vencimiento.
  - Solo pagos completos. El creador también participa y paga el sobrante de la división.
  - Cualquiera puede retirarse antes de la fecha límite, haya pagado o no. Si pagó, se le devuelve en el acto. La meta baja, y quienes ya pagaron pasan a `por_confirmar`: deben aceptar los términos nuevos. Un retiro nunca completa la bolsa.
  - Nada se envía sin consentimiento. Al vencer, quien no está en `pagado` recupera su dinero; con la política de transferir se envía lo de quienes sí están en `pagado`, y con la de devolver se devuelve todo.
  - Si el creador cancela: con la política de devolver, se devuelve todo; con la de transferir, cada uno confirma o se retira hasta la fecha límite.
- **Fuera de alcance:** la lista completa está en `SPEC.md`, sección 11. Los agentes no implementan ni proponen nada de esa lista.

## 3. Reglas que no se negocian

El texto exacto está en `AGENTS.md`. En resumen:

1. El dinero se guarda y se calcula como entero (pesos). Nunca float.
2. Todo movimiento pasa por un único servicio de libro contable, en partida doble: cada transacción suma cero. El saldo se modifica solo con `saldo = saldo + :delta` en SQL.
3. Cada operación de dinero es atómica: una sola transacción de base de datos, todo o nada.
4. Los movimientos no se editan ni se borran.
5. Un solo orden de bloqueo: sesión, clave de idempotencia, bolsa (`FOR UPDATE`) y cuentas por id ascendente (`FOR NO KEY UPDATE`, una por sentencia), siempre leyendo con `populate_existing`.
6. Las operaciones que pueden mover dinero (cargar, transferir, aportar y retirarse) llevan clave de idempotencia: reintentar no duplica.
7. La división siempre suma exactamente el total, de forma determinista.
8. Cada bolsa empieza y termina en cero, y su configuración no cambia.
9. No queda en el repo código que yo no pueda explicar.

## 4. Documentos y estructura del repo

```
cuadre/
  README.md          # en mi voz, con los 8 puntos del reto
  SPEC.md            # fuente de verdad del producto (secciones 0 a 11)
  AGENTS.md          # reglas y protocolo para los agentes (única fuente de reglas)
  CLAUDE.md          # importa AGENTS.md y agrega lo propio de Claude Code
  DECISIONS.md       # bitácora: decisión, alternativas, por qué
  AI_LOG.md          # bitácora de IA: qué pedí, qué decidí yo, errores de la IA
  docs/              # este roadmap, FLUJO.md y la guía del stack
  docker-compose.yml
  Makefile           # make up, make test, make check, make seed
  .env.example       # sin llaves reales
  backend/
    app/api/         # endpoints
    app/services/    # libro contable, usuarios, bolsas y barrido
    app/domain/      # reglas puras: división, estados de la bolsa, validaciones
    app/db/          # modelos, sesión, migraciones e invariantes
    tests/           # domain, db, services, api, concurrencia, barrido
  frontend/          # Angular, solo si alcanza el tiempo
```

- **DECISIONS.md** y **AI_LOG.md** se llenan mientras trabajo. De ahí salen los puntos 1, 6 y 7 del README.
- **README.md** lo redacto yo. La IA solo corrige ortografía.

## 5. Cómo trabajar con los agentes

- **Yo decido:** alcance, reglas, qué se recorta y si un cambio se acepta.
- **Claude Code ejecuta** cada tarea de la sección 6 con el ciclo de `docs/FLUJO.md`.
- **Kiro audita** en una sesión aparte, solo las tareas que mueven dinero (T6, T11 y T14), para no gastar tiempo en el resto.

## 6. Roadmap paso a paso

Me quedan unas **8 horas**. El plan suma 7 horas y 55 minutos desde que empieza el reloj, así que no hay margen: los puntos de control de la sección 7 dicen qué recortar si voy atrasado. Cada tarea es un ciclo completo de `docs/FLUJO.md` (plan, pruebas, implementación, diff y commit) y lleva las secciones del SPEC que el agente debe leer.

Las pruebas no son una fase aparte: cada tarea escribe las suyas antes del código. Toda prueba que toca la base termina corriendo las invariantes desde T4.

### Fase 1. Especificación (hecha)

SPEC.md, AGENTS.md y DECISIONS.md cerrados, con dos rondas de diseño y una auditoría con otro modelo.

### Fase 2. Base de datos (85 min)

| Tarea | Qué incluye | SPEC | Hecho cuando | Min |
| --- | --- | --- | --- | --- |
| **T1. Infraestructura de base y pruebas** | Alembic inicializado; motor y sesión de SQLAlchemy desde variables de entorno; fixture de sesión que crea `cuadre_test` con `alembic upgrade head` y la borra al final (negándose si el nombre no termina en `_test`); fixture por prueba que vacía las tablas | 10.2 | `pytest` corre `test_health` contra una base creada y borrada por el fixture | 20 |
| **T2. Tablas y restricciones** | Una migración con todas las tablas: cuentas (con la cuenta de sistema), usuarios, sesiones, transacciones, movimientos, claves de idempotencia, bolsas y participantes; todas las restricciones con nombre, índices únicos parciales e índices | 3.1 a 3.5 | La migración corre de cero y cada restricción tiene una prueba que la viola: monto negativo, saldo negativo, aporte duplicado, objetivo `sistema`, entre otras | 40 |
| **T3. Invariantes y `make check`** | `app/db/invariantes.py` con L1 a L8 y B1 a B11; fixture que las corre al terminar cada prueba; `make check`; `Makefile` con `up`, `test` y `check`; pruebas de detección al menos para L1 a L4 | 4, 10.5 | `make check` pasa en una base vacía y cada prueba de detección ve su violación | 25 |

### Fase 3. Núcleo contable (95 min)

| Tarea | Qué incluye | SPEC | Hecho cuando | Min |
| --- | --- | --- | --- | --- |
| **T4. Dominio base y errores** | Excepciones de dominio con su `codigo`; validación de monto, tope y transferencia a uno mismo; prueba de fronteras de capas | 2.1, 2.6, 5.6 | Las validaciones puras pasan sin base de datos y la prueba de capas está en verde | 15 |
| **T5. Usuarios y sesiones** | Registro con scrypt; login con token de `secrets` guardado como SHA-256; renovar; logout; autenticación como primer paso de cada caso de uso | 1.4, 5.2, 5.3 | Registro repetido da `registro_rechazado` (incluida la llave de cuentas), login correcto e incorrecto, token vencido da 401 | 25 |
| **T6. Libro: cargar y transferir** | Envoltorio de reintentos con contador; idempotencia con `ON CONFLICT DO NOTHING RETURNING` y hash; bloqueo por cuenta con `key_share=True` y `populate_existing`; saldo relativo; verificación de partida doble | 2.3 a 2.5, 5.4 a 5.6 | Casos normales y de error, misma clave con mismo y otro cuerpo, y la prueba de lectura fresca (10.3) en verde | 45 |
| **T7. Saldo, historial y concurrencia del núcleo** | Saldo; historial con desempate y rango; pruebas con hilos de las filas del núcleo de 8.4 (100 transferencias, misma clave, transferencias cruzadas) con cero reintentos | 5.7, 5.8, 8.4, 10.4 | Las 100 transferencias dan exactamente 50 y 50, saldo final 0 e invariantes en verde | 15 |

### Fase 4. API del núcleo (30 min)

| Tarea | Qué incluye | SPEC | Hecho cuando | Min |
| --- | --- | --- | --- | --- |
| **T8. Endpoints del núcleo** | `/usuarios`, `/sesiones`, `/cuenta`, `/cuenta/movimientos`, `/cargas` y `/transferencias`; traducción de errores a `{codigo, mensaje, campos}`; 401, 404 y 405 en ese formato; CORS; validación con `fullmatch` | 2.6, 9.1 a 9.3 | Hago el flujo completo del núcleo desde `/docs`, y `"ana\n"` da 422 | 30 |

### Fase 5. Bolsas (90 min)

| Tarea | Qué incluye | SPEC | Hecho cuando | Min |
| --- | --- | --- | --- | --- |
| **T9. Dominio de bolsas** | División con propiedades de Hypothesis; validaciones de creación; transiciones de estado puras | 3.7, 6.2 a 6.4 | Las propiedades de la división y las transiciones pasan sin base de datos | 20 |
| **T10. Crear y consultar bolsas** | Crear (404 por participante o cuenta objetivo, `nombre_en_uso`); detalle con totales y mi participación; mis bolsas; mis movimientos con la bolsa | 6.2, 9.4 | Una bolsa de $90.000 entre tres se crea con partes de $30.000 y cada participante ve solo lo suyo | 20 |
| **T11. Aportar, retirarse y confirmar** | Las tres operaciones con transferencia final automática, `por_confirmar`, cierre en cero comprobado, cuenta objetivo bloqueada solo si se completa y orden estado-plazo; pruebas secuenciales de las filas de bolsas de 8.4 | 6.5 a 6.8, 8.2, 8.4 | Una bolsa se completa y transfiere una sola vez; un retiro deja a los demás por confirmar; invariantes en verde | 40 |
| **T12. Concurrencia de bolsas** | Pruebas con hilos: dos aportes finales, dos confirmaciones finales y retiro de los dos últimos activos, repetidas 10 veces | 8.4, 10.4 | Exactamente una transferencia final, cero reintentos e invariantes en verde | 10 |

### Fase 6. Cancelación y vencimiento (50 min)

| Tarea | Qué incluye | SPEC | Hecho cuando | Min |
| --- | --- | --- | --- | --- |
| **T13. Cancelar** | Cancelación con ambas políticas, el estado `cancelada` y sus pruebas secuenciales de 8.4 | 7.1, 7.3 | Con la política de devolver la bolsa pasa a `liquidando` o `cerrada`; con la de transferir, a `cancelada` con los pagados por confirmar | 20 |
| **T14. Barrido** | Los tres pasos como funciones (preparar, devolver y cerrar) con las verificaciones del paso 3; `procesar_vencidas(ahora)`; hilo en el `lifespan` con intervalo y bandera; pruebas de 10.7 | 7.2 a 7.4, 2.8, 2.9, 10.7 | Ambas políticas liquidan bien, la reanudación no paga de más y una bolsa que falla no detiene a las demás | 30 |

### Fase 7. API de bolsas (25 min)

| Tarea | Qué incluye | SPEC | Hecho cuando | Min |
| --- | --- | --- | --- | --- |
| **T15. Endpoints de bolsas** | Las rutas de bolsas de 9.2, con 403 y 404, id no UUID, cuerpos ignorados y las respuestas de 9.4 | 9.2, 9.4 | Hago desde `/docs` la demo completa: crear, aportar, retirarse, confirmar y ver la transferencia final | 25 |

### Fase 8. Cierre técnico (25 min)

| Tarea | Qué incluye | Hecho cuando | Min |
| --- | --- | --- | --- |
| **T16. Datos de demo y prueba limpia** | `make seed` con la cena de cumpleaños y los roommates; clonar el repo en una carpeta limpia y correrlo siguiendo solo el README | Todo arranca con `make up`, `make test` y `make check` desde cero | 15 |
| **T17. Auditoría final** | Kiro, en sesión nueva: `AUDITA: el libro contable y las bolsas`, solo hallazgos de gravedad alta | No queda ningún hallazgo alto abierto | 10 |

### Fase 9. README, video y entrega (70 min)

- **README (40 min):** los ocho puntos, sacados de `DECISIONS.md`, `AI_LOG.md` y `SPEC.md` (la tabla 10.1 es el punto 2 y la sección 11 son los puntos 3 y 6). Incluye cómo correrlo en tres comandos y el diagrama del flujo del dinero (SPEC 0.1).
- **Video (20 min):** guion en la sección 10.
- **Entrega (10 min):** correo de la sección 11, con margen antes del cierre.

### Solo si sobra tiempo, en este orden

1. GitHub Actions con PostgreSQL como servicio (10 min).
2. Romper el código a propósito con los tres casos de SPEC 10.6 y anotar el resultado en el README (20 min).
3. Prueba de humo del hilo del barrido (10 min).
4. Frontend en Angular (SPEC 9.5): no empezar con menos de 3 horas libres.

## 7. Puntos de control

El reloj empieza al terminar de hacer commit de los documentos (unos 15 minutos).

| Al llegar a | Debería ir en | Si voy atrasado |
| --- | --- | --- |
| 1:45 | T3 terminada | Reducir las pruebas de detección a L3 y L4 |
| 3:30 | T7 terminada | Recorte 1 |
| 4:00 | T8 terminada | Recorte 2 |
| 5:30 | T12 terminada | Recorte 3 |
| 6:20 | T15 terminada | Dejar lo que falte, saltar T17 y pasar a T16 y la fase 9: el README y el video no se recortan |

## 8. Orden de recorte

Cada recorte se anota en `DECISIONS.md` y se declara en el README como decisión, no como olvido.

1. **Renovación de sesión y pruebas de detección más allá de L4.** El usuario vuelve a iniciar sesión cada 20 minutos.
2. **Cancelación con la política de transferir.** Cancelar siempre devuelve todo; el estado `cancelada` no se implementa.
3. **El hilo del barrido.** `procesar_vencidas(ahora)` se implementa y se prueba igual, pero se ejecuta con un comando y no solo cada 60 s.

Nunca se recortan: el libro contable, la idempotencia, la prueba de las 100 transferencias, las bolsas con aporte, retiro, confirmación y transferencia final, las invariantes, el README ni el video.

## 9. README: los ocho puntos

1. Decisiones clave y por qué.
2. Cómo sé que no se pierde un peso: riesgos, defensas y evidencia (SPEC 10.1).
3. Qué dejé fuera y por qué (SPEC 11.1 y los recortes).
4. Qué haría distinto con más tiempo.
5. Qué no sé. Con honestidad.
6. Supuestos (SPEC 11.2).
7. Cómo usé la IA, con al menos un error real y cómo lo detecté (H1 de la auditoría es el principal).
8. Qué aprendí.

Además: cómo correr el proyecto en tres comandos y el diagrama del flujo del dinero.

## 10. Video (máximo 5 minutos, sin leer)

- **0:00 a 0:30:** qué es Cuadre y qué problema resuelve.
- **0:30 a 2:30:** demo desde `/docs` (o desde el frontend, si existe) con los datos de `make seed`: cargar saldo, la bolsa de la cena con pagos, un retiro con devolución que deja a los demás por confirmar, la confirmación que completa y transfiere, y una segunda bolsa cancelada.
- **2:30 a 4:00:** por qué no se pierde un peso: las pruebas, la de las 100 transferencias y `make check`.
- **4:00 a 5:00:** cómo usé la IA (la auditoría y H1), qué dejé fuera y qué haría después.

Ensayo una vez antes de grabar y verifico que el enlace se pueda abrir sin iniciar sesión.

## 11. Entrega

Correo a tech-team@habicapital.com con:

1. Mi nombre.
2. Enlace al repo del reto.
3. Enlace al video.
4. Mi CV.
5. Enlace a mi GitHub personal, con este repo fijado en el perfil.

## 12. Preparación para la entrevista

Serán 60 minutos de pair programming sobre mi código con un cambio que no anticipé, y 30 de conversación sobre decisiones. Cambios probables:

- Agregar una comisión por transferencia.
- Poner un límite diario por cuenta.
- Reversar una transferencia.
- Permitir pagos parciales en una bolsa.
- Agregar un participante a una bolsa ya creada.
- Exportar el historial.

Para cada módulo debo poder responder: qué hace, por qué está así, qué pasaría si falla y cómo lo probé. También: cómo se cumple ACID en cada operación y por qué la liquidación de una bolsa se reparte en varias transacciones.

## 13. Riesgos a tener presentes

- Querer construir demasiado. Con 8 horas, el frontend casi seguro queda fuera.
- Aceptar código de la IA sin leerlo, sobre todo en T6 y T11.
- Dejar el README y el video para la última hora.
- Subir una llave al repo público.
- Que el proyecto no corra en una máquina limpia.
- Inventar un error de la IA para el README. Debe ser real.
