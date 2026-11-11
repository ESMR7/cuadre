# Roadmap del reto técnico HabiCapital

Plan de trabajo de Edy Santiago Martínez Rojas para las 72 horas del reto. Stack: Python, FastAPI, PostgreSQL, React con TypeScript.

## 1. Nombre del proyecto

**Cuadre.** Tiene doble sentido: "cuadrar cuentas" entre amigos (el reto habla de la profesora que pierde horas "cuadrando") y el cuadre contable, que es la garantía de que el sistema no pierde un peso. Repo: `cuadre`.

## 2. Alcance

- **Núcleo obligatorio:** crear cuenta, cargar saldo (simulado), transferir, consultar saldo y ver historial.
- **Mi propuesta de valor (una sola cosa):** cobros en grupo. Un grupo, un cobro dividido entre sus miembros, y recurrencia opcional.
- **Capa de IA (última y recortable):** crear un cobro escribiéndolo en lenguaje natural. La IA propone un borrador, el código lo valida y el usuario lo confirma.
- **Fuera de alcance (lo declaro en el README):** débito automático sin aprobación, pasarela real, verificación de identidad, cumplimiento regulatorio, app móvil, múltiples monedas.

## 3. Reglas que no se negocian

1. El dinero se guarda y se calcula como entero (pesos). Nunca float.
2. Todo movimiento pasa por un único servicio de libro contable, en partida doble: cada transacción suma cero.
3. Cada operación de dinero es atómica: una sola transacción de base de datos, todo o nada.
4. Los movimientos no se editan ni se borran. Los errores se corrigen con movimientos compensatorios.
5. Las cuentas se bloquean siempre en el mismo orden (por id) para evitar saldos negativos y deadlocks.
6. Toda operación lleva clave de idempotencia: reintentar no duplica.
7. La división de un cobro siempre suma exactamente el total, de forma determinista.
8. La IA nunca ejecuta ni decide un movimiento de dinero.
9. No queda en el repo código que yo no pueda explicar.

## 4. Documentos y estructura del repo

```
cuadre/
  README.md          # en mi voz, con los 8 puntos del reto
  SPEC.md            # entidades, invariantes, flujos, decisiones de producto
  CLAUDE.md          # reglas fijas para el agente (o el archivo equivalente de mi herramienta)
  DECISIONS.md       # bitácora corta: decisión, alternativas, por qué
  AI_LOG.md          # bitácora de IA: qué pedí, qué decidí yo, errores de la IA
  docker-compose.yml
  Makefile           # make up, make test, make check, make seed
  .env.example       # sin llaves reales
  backend/
    app/api/         # endpoints
    app/services/    # libro contable, cobros, recurrencia
    app/domain/      # reglas puras: división, validaciones
    app/db/          # modelos y migraciones
    app/ai/          # parser de cobros (real y falso)
    tests/
  frontend/
```

- **SPEC.md** lo escribo yo antes de programar. Es la fuente de verdad.
- **DECISIONS.md** y **AI\_LOG.md** los lleno mientras trabajo, no al final. De ahí salen los puntos 1, 6 y 7 del README.
- **README.md** lo redacto yo. La IA solo corrige ortografía.

## 5. Cómo trabajar con los agentes

Reparto de responsabilidades:

- **Yo decido:** alcance, invariantes, modelo de datos, reglas de producto, qué se recorta, y si un cambio se acepta.
- **El agente ejecuta:** código repetitivo, migraciones, pruebas a partir de mis invariantes, interfaz, y borradores de documentación técnica.
- **El agente audita:** en una sesión nueva y sin contexto previo, busca errores en lo que otra sesión escribió.

Dinámica en cada tarea:

1. Le doy el SPEC y las reglas, y le pido un plan antes de escribir código.
2. Reviso el plan y lo ajusto.
3. Pido las pruebas primero y luego la implementación hasta que pasen.
4. Leo el cambio completo antes de aceptarlo. Si no entiendo algo, pido que me lo explique o lo reescribo más simple.
5. Hago commit pequeño con un mensaje claro.
6. Anoto en AI\_LOG.md cualquier error o casi-error de la IA y cómo lo detecté.

## 6. Roadmap paso a paso

Las pruebas no son una fase aparte: se escriben dentro de cada fase, antes del código. Las horas son una guía para unas 35 horas de trabajo efectivo.

### Fase 0. Preparación (1 hora)

- **Yo:** creo el repo público, instalo Docker y Python, consigo la API key del modelo, calculo mi hora límite de entrega.
- **Agente:** genera el esqueleto del proyecto, docker-compose con PostgreSQL y el Makefile.
- **Hecho cuando:** `make up` levanta la app vacía y la base de datos.

### Fase 1. Especificación (2 horas)

- **Yo:** escribo SPEC.md: entidades, invariantes, flujos de transferencia y de cobro, supuestos (COP entero, quién recibe el peso sobrante, qué pasa sin fondos).
- **Agente:** ataca el diseño. Le pido que liste todo lo que puede salir mal con el dinero y que señale huecos.
- **Hecho cuando:** cada riesgo tiene una defensa escrita o está declarado fuera de alcance.

### Fase 2. Base de datos (2 horas)

- **Yo:** defino las tablas: usuarios, cuentas, transacciones, movimientos, grupos, miembros, cobros, partes, plantillas de recurrencia.
- **Agente:** escribe modelos y migraciones con las restricciones: montos mayores que cero, saldo no negativo, claves únicas de idempotencia y de periodo.
- **Hecho cuando:** la migración corre de cero y la base rechaza un monto negativo y un duplicado.

### Fase 3. Núcleo contable (6 horas)

- **Yo:** defino las pruebas que deben existir y reviso con lupa esta parte. Es la más importante del reto.
- **Agente:** implementa el servicio de libro contable: cargar saldo desde una cuenta de sistema, transferir, saldo e historial.
- **Pruebas:** casos normales y de borde, reintento con la misma clave, 100 transferencias simultáneas, y la verificación de invariantes.
- **Hecho cuando:** `make check` confirma que todas las transacciones suman cero y que cada saldo es igual a la suma de sus movimientos.

### Fase 4. API (2 horas)

- **Agente:** endpoints de FastAPI, validación estricta de entradas, errores claros y autenticación sencilla.
- **Yo:** decido el nivel de autenticación y lo justifico en DECISIONS.md.
- **Hecho cuando:** puedo hacer el flujo completo del núcleo desde la documentación interactiva de la API.

### Fase 5. Grupos y cobros divididos (6 horas)

- **Yo:** decido las reglas: tipos de reparto, estados del cobro, quién puede cancelar, qué pasa si un miembro sale del grupo.
- **Agente:** implementa grupos, cobros, partes y el pago de una parte como transferencia normal del libro contable.
- **Pruebas:** pruebas de propiedades de la división (la suma siempre da el total), estados del cobro y pagos repetidos.
- **Hecho cuando:** un cobro de $100.000 entre 3 queda completado y los invariantes siguen en verde.

### Fase 6. Recurrencia (3 horas)

- **Agente:** plantillas y la función `procesar_pendientes(ahora)`, que recibe la hora como parámetro.
- **Pruebas:** ejecutar dos veces el mismo periodo no duplica, meses con menos días, zona horaria de Bogotá.
- **Hecho cuando:** simulo tres meses y aparecen exactamente tres cobros.

### Fase 7. IA para crear cobros (3 horas, recortable)

- **Yo:** defino el esquema del borrador y preparo 15 a 20 frases de evaluación, incluidas ambiguas.
- **Agente:** implementa el parser con salida estructurada, la versión falsa para pruebas y la vista previa con confirmación.
- **Hecho cuando:** tengo la tabla de resultados de la evaluación y la app funciona igual si el modelo falla.

### Fase 8. Interfaz mínima (4 horas)

- **Agente:** tres o cuatro pantallas: mi cuenta e historial, transferir, grupos, cobro.
- **Yo:** reviso que no haya cálculos de dinero en el navegador y que entiendo el código.
- **Hecho cuando:** puedo grabar la demo completa sin tocar la terminal.

### Fase 9. Endurecimiento (2 horas)

- Auditoría en sesión nueva: concurrencia, redondeo, duplicados, entradas maliciosas.
- Corro todo desde cero en una carpeta limpia siguiendo solo el README.
- Reviso que no haya llaves ni datos personales en el historial de git.

### Fase 10. README, video y entrega (4 horas)

- Escribo el README con los ocho puntos, usando DECISIONS.md y AI\_LOG.md.
- Grabo el video y envío el correo con margen de varias horas.

## 7. Qué automatizar

- `make up`: levanta todo con Docker.
- `make test`: corre todas las pruebas.
- `make check`: verifica los invariantes del libro contable.
- `make seed`: carga datos de ejemplo para la demo (los roommates, la cena).
- Formato y revisión de estilo automáticos antes de cada commit.
- Integración continua en GitHub Actions: pruebas en cada push. La insignia en verde es evidencia visible.

## 8. Orden de recorte si falta tiempo

1. Capa de IA (fase 7).
2. Interfaz: uso la documentación interactiva de la API para la demo.
3. Recurrencia: queda diseñada en el SPEC y declarada como pendiente.
4. Tipos de reparto: dejo solo el reparto igual.

Nunca se recortan el núcleo contable, sus pruebas ni el README.

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
- **0:30 a 2:30:** demo: crear cuentas, cargar, transferir, crear un grupo y un cobro dividido, pagar, ver historial.
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
- Cancelar un cobro que ya tiene pagos parciales.
- Cambiar el reparto de igual a porcentajes.
- Exportar el historial.

Para cada módulo debo poder responder: qué hace, por qué está así, qué pasaría si falla y cómo lo probé.

## 13. Riesgos a tener presentes

- Querer construir demasiado. Una sola cosa, bien hecha.
- Aceptar código de la IA sin leerlo.
- Dejar el README y el video para la última hora.
- Subir la API key al repo público.
- Que el proyecto no corra en una máquina limpia.
- Inventar un error de la IA para el README. Debe ser real.
