# Roadmap del reto técnico HabiCapital

Plan de trabajo de Edy Santiago Martínez Rojas para las 72 horas del reto. Stack: Python, FastAPI, PostgreSQL, React con TypeScript.

## 1. Nombre del proyecto

**Cuadre.** Tiene doble sentido: "cuadrar cuentas" entre amigos (el reto habla de la profesora que pierde horas "cuadrando") y el cuadre contable, que es la garantía de que el sistema no pierde un peso. Repo: `cuadre`.

## 2. Alcance

- **Núcleo obligatorio:** crear cuenta, cargar saldo (simulado), transferir, consultar saldo y ver historial.
- **Mi propuesta de valor (una sola cosa): bolsas.** Un cobro en grupo con una cuenta común. La app divide el total de forma exacta, cada participante paga su parte completa o se retira, y cuando se reúne todo, el dinero se transfiere a la cuenta objetivo que eligió el creador.
- **Reglas de producto de las bolsas:**
  - Cada bolsa es de un solo uso y su configuración no cambia después de crearla: partes, cuenta objetivo, fecha límite y política de vencimiento.
  - Solo pagos completos. Cada participante decide si acepta y paga su parte.
  - Cualquiera puede retirarse antes de la fecha límite, haya pagado o no. Si pagó, se le devuelve. La meta baja en su parte.
  - Si no se completa a tiempo, se aplica la política elegida al crear la bolsa: transferir lo reunido o devolverlo.
  - Si el creador cancela: con política "devolver", se devuelve todo; con "transferir", cada participante que pagó decide si su aporte se envía o se le devuelve.
- **Por definir en el SPEC:** el plazo para decidir tras una cancelación y qué pasa si alguien no decide (propuesta: 48 horas y devolver), y a quién le toca el peso sobrante de la división.
- **Fuera de alcance (lo declaro en el README):** cobros recurrentes, creación de cobros con IA, pagos parciales, bolsas reutilizables, reverso después de transferir, débito automático, pasarela real, verificación de identidad, cumplimiento regulatorio, app móvil y múltiples monedas.

## 3. Reglas que no se negocian

1. El dinero se guarda y se calcula como entero (pesos). Nunca float.
2. Todo movimiento pasa por un único servicio de libro contable, en partida doble: cada transacción suma cero.
3. Cada operación de dinero es atómica: una sola transacción de base de datos, todo o nada.
4. Los movimientos no se editan ni se borran. Los errores se corrigen con movimientos compensatorios.
5. Un solo orden de bloqueo: primero la bolsa y después las cuentas por id, para evitar saldos negativos y deadlocks.
6. Toda operación lleva clave de idempotencia: reintentar no duplica.
7. La división siempre suma exactamente el total, de forma determinista.
8. Cada bolsa empieza y termina en cero, y su configuración no cambia después de crearla.
9. No queda en el repo código que yo no pueda explicar.

## 4. Documentos y estructura del repo

```
cuadre/
  README.md          # en mi voz, con los 8 puntos del reto
  SPEC.md            # entidades, invariantes, flujos, decisiones de producto
  AGENTS.md          # reglas y protocolo para los agentes (única fuente)
  CLAUDE.md          # importa AGENTS.md y agrega lo propio de Claude Code
  DECISIONS.md       # bitácora corta: decisión, alternativas, por qué
  AI_LOG.md          # bitácora de IA: qué pedí, qué decidí yo, errores de la IA
  docker-compose.yml
  Makefile           # make up, make test, make check, make seed
  .env.example       # sin llaves reales
  backend/
    app/api/         # endpoints
    app/services/    # libro contable, bolsas y vencimientos
    app/domain/      # reglas puras: división, estados de la bolsa, validaciones
    app/db/          # modelos y migraciones
    tests/
  frontend/
```

- **SPEC.md** lo escribo yo antes de programar. Es la fuente de verdad.
- **DECISIONS.md** y **AI_LOG.md** los lleno mientras trabajo, no al final. De ahí salen los puntos 1, 6 y 7 del README.
- **README.md** lo redacto yo. La IA solo corrige ortografía.

## 5. Cómo trabajar con los agentes

Reparto de responsabilidades:

- **Yo decido:** alcance, invariantes, modelo de datos, reglas de producto, qué se recorta, y si un cambio se acepta.
- **El agente ejecuta:** código repetitivo, migraciones, pruebas a partir de mis invariantes, interfaz, y borradores de documentación técnica.
- **El agente audita:** en una sesión nueva y sin contexto previo, busca errores en lo que otra sesión escribió.

El detalle del ciclo de cada tarea está en `docs/FLUJO.md`.

## 6. Roadmap paso a paso

Las pruebas no son una fase aparte: se escriben dentro de cada fase, antes del código. Las horas son una guía para unas 33 horas de trabajo efectivo.

### Fase 0. Preparación (hecha)

Repo, Docker con PostgreSQL, API mínima, prueba de `/health` y archivos para los agentes.

### Fase 1. Especificación (3 horas)

- **Yo:** escribo SPEC.md: entidades, invariantes, estados de la bolsa, flujos y supuestos (COP entero, peso sobrante, plazo de decisión tras cancelar).
- **Agente:** ataca el diseño. Le pido que liste todo lo que puede salir mal con el dinero y que señale huecos.
- **Hecho cuando:** cada riesgo tiene una defensa escrita o está declarado fuera de alcance.

### Fase 2. Base de datos (2 horas)

- **Yo:** defino las tablas: usuarios, cuentas, transacciones, movimientos, bolsas y participantes.
- **Agente:** escribe modelos y migraciones con las restricciones: montos mayores que cero, saldo no negativo, claves únicas de idempotencia y cierre único de cada bolsa.
- **Hecho cuando:** la migración corre de cero y la base rechaza un monto negativo y un duplicado.

### Fase 3. Núcleo contable (6 horas)

- **Yo:** defino las pruebas que deben existir y reviso con lupa esta parte. Es la más importante del reto.
- **Agente:** implementa el servicio de libro contable: cargar saldo desde una cuenta de sistema, transferir, saldo e historial.
- **Pruebas:** casos normales y de borde, reintento con la misma clave, 100 transferencias simultáneas, y la verificación de invariantes.
- **Hecho cuando:** `make check` confirma que todas las transacciones suman cero y que cada saldo es igual a la suma de sus movimientos.

### Fase 4. API del núcleo (2 horas)

- **Agente:** endpoints de FastAPI, validación estricta de entradas, errores claros y autenticación sencilla.
- **Yo:** decido el nivel de autenticación y lo justifico en DECISIONS.md.
- **Hecho cuando:** puedo hacer el flujo completo del núcleo desde la documentación interactiva de la API.

### Fase 5. Bolsas (6 horas)

- **Yo:** reviso que los estados y las reglas del SPEC estén bien traducidos a pruebas.
- **Agente:** crear una bolsa con división exacta, aportar la parte completa, retirarse (con devolución si ya pagó) y transferir a la cuenta objetivo al completarse.
- **Pruebas:** propiedades de la división, retiro del último pendiente que completa la bolsa, retiro de todos, pagos repetidos y concurrencia (dos aportes finales a la vez, aporte contra retiro).
- **Hecho cuando:** una bolsa de $100.000 entre 3 se completa, se transfiere una sola vez y los invariantes siguen en verde.

### Fase 6. Cancelación y vencimiento (4 horas)

- **Agente:** cancelación con ambas políticas, decisión por participante cuando la política es transferir, y `procesar_vencidas(ahora)`, que recibe la hora como parámetro.
- **Pruebas:** cancelar devuelve exactamente lo aportado, procesar dos veces no duplica, decisiones mezcladas (unos envían y otros piden devolución), vencimiento contra último aporte simultáneo.
- **Hecho cuando:** después de cancelar o vencer, cada bolsa cerrada queda en cero y cada participante recuperó o envió exactamente lo suyo.

### Fase 7. Interfaz mínima (4 horas)

- **Agente:** tres o cuatro pantallas: mi cuenta e historial, transferir, crear bolsa, y detalle de bolsa con pagar, retirarse y cancelar.
- **Yo:** reviso que no haya cálculos de dinero en el navegador y que entiendo el código.
- **Hecho cuando:** puedo grabar la demo completa sin tocar la terminal.

### Fase 8. Endurecimiento (2 horas)

- Auditoría en sesión nueva: concurrencia, redondeo, duplicados, entradas maliciosas.
- Corro todo desde cero en una carpeta limpia siguiendo solo el README.
- Reviso que no haya llaves ni datos personales en el historial de git.

### Fase 9. README, video y entrega (4 horas)

- Escribo el README con los ocho puntos, usando DECISIONS.md y AI_LOG.md.
- Grabo el video y envío el correo con margen de varias horas.

## 7. Qué automatizar

- `make up`: levanta todo con Docker.
- `make test`: corre todas las pruebas.
- `make check`: verifica los invariantes del libro contable y que toda bolsa cerrada esté en cero.
- `make seed`: carga datos de ejemplo para la demo (la cena de cumpleaños, los roommates).
- Formato y revisión de estilo automáticos antes de cada commit.
- Integración continua en GitHub Actions: pruebas en cada push. La insignia en verde es evidencia visible.

## 8. Orden de recorte si falta tiempo

1. Interfaz: uso la documentación interactiva de la API para la demo.
2. Decisión por participante al cancelar: la cancelación siempre devuelve, y lo declaro.
3. Vencimiento automático: el creador cierra la bolsa a mano.

Nunca se recortan el núcleo contable, las bolsas con retiro y transferencia, sus pruebas ni el README.

## 9. README: los ocho puntos

1. Decisiones clave y por qué.
2. Cómo sé que no se pierde un peso: riesgos, defensas y evidencia (pruebas, invariantes, estrés).
3. Qué dejé fuera y por qué.
4. Qué haría distinto con más tiempo.
5. Qué no sé. Con honestidad.
6. Supuestos.
7. Cómo usé la IA, con al menos un error real y cómo lo detecté.
8. Qué aprendí.

Además: cómo correr el proyecto en tres comandos y un diagrama simple del flujo del dinero.

## 10. Video (máximo 5 minutos, sin leer)

- **0:00 a 0:30:** qué es Cuadre y qué problema resuelve.
- **0:30 a 2:30:** demo: crear cuentas y cargar saldo, crear la bolsa de la cena, pagos, un retiro con devolución, la bolsa completa transfiriéndose a la cuenta objetivo, y una segunda bolsa cancelada.
- **2:30 a 4:00:** por qué no se pierde un peso: muestro las pruebas, la de concurrencia y `make check`.
- **4:00 a 5:00:** cómo usé la IA, qué dejé fuera y qué haría después.

Ensayo dos veces antes de grabar y verifico que el enlace se pueda abrir sin iniciar sesión.

## 11. Entrega

Correo a tech-team@habicapital.com con:

1. Mi nombre.
2. Enlace al repo del reto.
3. Enlace al video.
4. Mi CV.
5. Enlace a mi GitHub personal, con este repo fijado en el perfil.

## 12. Preparación para la entrevista

Serán 60 minutos de pair programming sobre mi código con un cambio que no anticipé, y 30 de conversación sobre decisiones. Practico con cambios como estos, con pantalla compartida y usando IA:

- Agregar una comisión por transferencia.
- Poner un límite diario por cuenta.
- Reversar una transferencia.
- Permitir pagos parciales en una bolsa.
- Agregar un participante a una bolsa ya creada.
- Exportar el historial.

Para cada módulo debo poder responder: qué hace, por qué está así, qué pasaría si falla y cómo lo probé.

## 13. Riesgos a tener presentes

- Querer construir demasiado. Una sola cosa, bien hecha.
- Aceptar código de la IA sin leerlo.
- Dejar el README y el video para la última hora.
- Subir una llave al repo público.
- Que el proyecto no corra en una máquina limpia.
- Inventar un error de la IA para el README. Debe ser real.
