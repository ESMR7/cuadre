# SPEC de Cuadre

> Fuente de verdad del producto. Si `AGENTS.md` y este archivo se contradicen, se detiene el trabajo y se resuelve.
>
> **Estado:** bloques 1 y 2 cerrados. Bloques 3 a 11 pendientes.

## 1. Alcance y supuestos

### 1.1 Moneda y montos

- Todos los montos son enteros en pesos colombianos (COP), sin centavos.
- La API solo acepta enteros JSON. `1000.0`, `"1000"` y `1e3` se rechazan con 422, sin conversión ni redondeo.
- El error de formato es responsabilidad de quien envía la petición, sea el frontend o un cliente directo de la API.

### 1.2 Usuarios y cuentas

- Cada usuario tiene exactamente una cuenta de tipo `personal`, creada en la misma transacción que el usuario.
- Tipos de cuenta: `personal`, `bolsa` y `sistema`.
- No hay retiros de dinero hacia fuera del sistema. Si se agregaran, serían un movimiento de la cuenta del usuario hacia la cuenta de sistema, con las mismas validaciones de una transferencia.

### 1.3 Cuenta de sistema

- Existe una sola, creada por migración. Es la contrapartida de toda carga de saldo.
- Cargar $X genera dos movimientos: +X en la cuenta del usuario y −X en la cuenta de sistema.
- Su saldo es el negativo de todo lo cargado: lo que el sistema les debe a los usuarios. Por eso la suma de los saldos de todas las cuentas es siempre cero.
- Restricciones de saldo:
  - Cuenta `sistema`: `saldo <= 0`.
  - Cuentas `personal` y `bolsa`: `saldo >= 0`.
- Se bloquea con `SELECT ... FOR UPDATE` como cualquier otra cuenta, así que las cargas simultáneas se procesan en fila. Es una limitación aceptada por tiempo y se declara como mejora futura.

### 1.4 Autenticación

**Contraseñas**
- Se guardan solo como hash lento con sal (`scrypt`, de la librería estándar). Nunca en claro.
- El login calcula el hash de la contraseña recibida y lo compara con el guardado.

**Sesiones y tokens**
- Un login exitoso genera un token aleatorio y lo devuelve una sola vez al cliente.
- En la base solo se guarda el hash SHA-256 del token. En cada petición el backend calcula el hash del token recibido y busca la sesión.
- El token viaja en cada petición en la cabecera `Authorization: Bearer <token>`.
- Una sola sesión activa por usuario: un login nuevo reemplaza la sesión anterior. La tabla de sesiones tiene `UNIQUE` sobre el usuario, para que dos logins simultáneos no dejen dos tokens válidos.
- El token expira 20 minutos después del login. Las peticiones normales no extienden el plazo.
- Renovación explícita: mientras el token siga vigente, el usuario puede pedir que se restablezcan los 20 minutos (la app le ofrece un botón para continuar cuando queda poco tiempo). La renovación conserva el mismo token y mueve su expiración a `ahora + 20 minutos`.
- Un token expirado no se puede renovar: el usuario inicia sesión otra vez y recibe un token nuevo.
- La expiración se compara con `ahora` (regla 10 del dinero), sin procesos que borren tokens.
- Cerrar sesión borra la sesión.
- Token ausente, inexistente o expirado: 401.

**Idempotencia y sesiones**
- La clave de idempotencia se asocia al usuario, no a la sesión: `UNIQUE (usuario_id, clave)`.
- Si el token expira entre una petición y su reintento, el cliente inicia sesión de nuevo, reintenta con la misma clave y recibe el resultado original sin mover dinero otra vez.

### 1.5 Límites

| Límite | Valor |
| --- | --- |
| Tope por carga, transferencia o aporte (operaciones que inicia un usuario) | $50.000.000 |
| Tope de devoluciones y de la transferencia final (movimientos que deriva el sistema) | Sin tope |
| Saldo máximo por cuenta | Sin tope |
| Participantes por bolsa | Entre 2 y 50 (constante configurable) |
| Total mínimo de una bolsa | $10.000, validado solo al crearla |
| Parte máxima por participante | $50.000.000 |
| Total máximo de una bolsa | $50.000.000 × participantes ($2.500.000.000 con 50) |

- Con estos límites cada parte es de al menos $200, así que ninguna parte es cero.
- Los retiros bajan la meta, pero nunca la dejan en cero mientras quede un participante. Si se retiran todos, se aplica la regla 5 de las bolsas.
- El tope por operación mantiene todos los saldos lejos de 2^53, el límite de enteros exactos en JavaScript.
- Una devolución nunca se rechaza por tope ni por saldo máximo.

### 1.6 Cuenta objetivo de las bolsas

- Se fija al crear la bolsa y no cambia.
- Puede ser cualquier cuenta `personal`, incluida la del creador. Nunca una cuenta `bolsa` ni la de sistema.
- Cada invitado ve los términos antes de entrar: su parte, el total, la cuenta objetivo, la fecha límite y la política de vencimiento.

### 1.7 Cancelación y vencimiento con devolución

- Se ejecutan como una transacción por participante, todas seguidas y sin esperar confirmación.
- Cada devolución respeta el orden de bloqueo: primero la fila de la bolsa y después sus dos cuentas por id ascendente.
- Lo que se le debe a cada participante se calcula desde el libro (aportes menos devoluciones), así que una devolución repetida o retomada no puede pagar de más.
- El estado intermedio (cancelada con saldo mayor que cero) y la reanudación tras una caída se definen en los bloques 6 y 7.

### 1.8 Preguntas abiertas del bloque 1

- **Credenciales:** ¿nombre de usuario o correo como identificador? Se define en el bloque 3.

---

## 2. Arquitectura

### 2.1 Capas

| Capa | Responsabilidad | No puede |
| --- | --- | --- |
| `api/` | Extrae el token y `Idempotency-Key` de las cabeceras, valida la forma (Pydantic estricto), lee `ahora`, entrega la sesión de base de datos y traduce excepciones a HTTP | Abrir transacciones, consultar, decidir reglas, hacer `commit` |
| `services/` | Dueño de la transacción: autentica, verifica la idempotencia, bloquea, lee el estado ya bloqueado, llama a `domain/`, escribe en el libro, confirma y reintenta. El servicio del libro contable es el único que inserta movimientos y cambia saldos | Importar FastAPI, leer la hora |
| `domain/` | Reglas puras: división, estados de la bolsa, validación de montos y tope, permisos con ids ya leídos | Importar SQLAlchemy o FastAPI, leer la hora |
| `db/` | Modelos, sesión, migraciones y restricciones | Lógica de negocio |

- La API solo recibe, valida la forma y delega. El servicio decide y escribe.
- Los únicos puntos que leen el reloj son la API y el hilo del barrido. Todo lo demás recibe `ahora`.
- Una prueba verifica que `domain/` no importa `sqlalchemy` ni `fastapi`, y que `services/` no importa `fastapi`.
- Saldo e historial también pasan por el servicio, en transacciones de solo lectura.

### 2.2 Flujo de una petición

```mermaid
sequenceDiagram
    participant C as Cliente
    participant A as api
    participant S as services
    participant D as domain
    participant B as PostgreSQL

    C->>A: HTTP con Bearer e Idempotency-Key
    A->>A: valida la forma y lee ahora
    A->>S: caso de uso con token, clave, datos y ahora
    S->>B: BEGIN
    S->>B: busca la sesion por hash del token
    alt token ausente o expirado
        S->>B: ROLLBACK
        S-->>A: SesionInvalida
        A-->>C: 401
    else sesion valida
        S->>B: INSERT de la clave con ON CONFLICT
        alt la clave ya existia
            S->>B: lee el hash guardado
            alt hash distinto
                S-->>A: ClaveReutilizada
                A-->>C: 409
            else hash igual
                S->>B: reconstruye la respuesta desde el libro
                S-->>A: resultado original
                A-->>C: 2xx
            end
        else clave nueva
            S->>B: FOR UPDATE de la bolsa y luego de las cuentas por id ascendente
            S->>B: lee el estado ya bloqueado
            S->>D: decide con estado, datos y ahora
            alt domain rechaza
                D-->>S: error de dominio
                S->>B: ROLLBACK y la clave se libera
                S-->>A: error
                A-->>C: 409 o 422
            else domain acepta
                D-->>S: resultado
                S->>B: movimientos en partida doble
                S->>B: COMMIT
                S-->>A: resultado
                A-->>C: 2xx
            end
        end
    end
```

Si el primer intento con una clave aún no confirma, el duplicado espera en el `INSERT` (lo hace el índice único) y después ve el resultado. Si el primero revierte, el duplicado inserta la clave y ejecuta la operación.

### 2.3 Transacción y reintentos

- Una sesión de base de datos por petición, creada por la API y nunca compartida entre hilos. La API no hace `commit`.
- Cada caso de uso, incluidas las lecturas, abre su transacción y la confirma o revierte. Aislamiento `READ COMMITTED`.
- La autenticación es el primer paso dentro de la transacción: sin sesión válida, 401 y `ROLLBACK`.
- Un envoltorio repite el caso de uso completo, autenticación incluida, solo ante `40P01` y `40001`, máximo 3 veces. Si se agotan: 503 `reintentos_agotados`, y el cliente puede repetir con la misma clave.
- Los errores de negocio y de validación no se reintentan.

### 2.4 Orden dentro de una operación

1. Sesión, solo lectura, sin bloqueo.
2. Clave de idempotencia, con `INSERT ... ON CONFLICT`.
3. Fila de la bolsa, con `FOR UPDATE`, si la operación toca una.
4. Cuentas por id ascendente, con `FOR UPDATE`, incluida la de quien paga.
5. Leer el estado, decidir en `domain/`, escribir en el libro y confirmar.

Nunca se bloquean dos bolsas en una misma transacción. Los ciclos solo podrían aparecer si algo rompe este orden.

### 2.5 Idempotencia

- El cliente genera un UUID v4 por cada intención del usuario y lo reutiliza en los reintentos. Viaja en `Idempotency-Key` y es obligatoria en toda operación que mueve dinero. Si falta: 400 `falta_clave_idempotencia`.
- Se guarda `UNIQUE (usuario_id, clave)`, el hash SHA-256 de (operación + ids de la ruta + cuerpo en forma canónica) y la referencia a la transacción del libro. El usuario ya está en la restricción, así que no entra en el hash.
- Misma clave y mismo hash: se devuelve el resultado original, reconstruido desde el libro. Nunca un error.
- Misma clave y otro hash: 409 `clave_reutilizada`.
- La clave solo persiste si la transacción confirma. Si la operación se rechaza y revierte, la clave queda libre.
- La verificación es un `INSERT ... ON CONFLICT`, nunca un `SELECT` seguido de un `INSERT`: la restricción `UNIQUE` es lo que cierra la carrera entre peticiones simultáneas.
- Las operaciones que origina el sistema (devoluciones del barrido) usan claves deterministas, definidas en el bloque 3.

### 2.6 Errores y HTTP

**Regla no negociable.** Si la petición es inválida por sí sola, sin importar el estado de ningún recurso, es **422**. Si la petición es válida pero choca con el estado actual de un recurso o con una regla que depende de ese estado, es **409**. Las dos categorías no se mezclan.

Todos los errores salen como `{"codigo": "...", "mensaje": "..."}`. El frontend y las pruebas usan `codigo`, no el número ni el texto.

| Situación | HTTP | `codigo` |
| --- | --- | --- |
| Forma inválida (decimal, texto, falta un campo) | 422 | `forma_invalida` |
| Monto cero o negativo | 422 | `monto_invalido` |
| Monto sobre el tope | 422 | `sobre_el_tope` |
| Transferencia a uno mismo | 422 | `transferencia_a_si_mismo` |
| Falta `Idempotency-Key` | 400 | `falta_clave_idempotencia` |
| Token ausente, inexistente o expirado; credenciales inválidas | 401 | `no_autenticado` |
| No figura en la bolsa o no es el creador | 403 | `sin_permiso` |
| Cuenta o bolsa inexistente | 404 | `no_encontrado` |
| Saldo insuficiente | 409 | `saldo_insuficiente` |
| Fecha límite pasada | 409 | `fuera_de_plazo` |
| Bolsa cerrada, ya pagó u otro estado que lo impide | 409 | `estado_invalido` |
| Misma clave con otro cuerpo | 409 | `clave_reutilizada` |
| Reintentos agotados | 503 | `reintentos_agotados` |

- Quien no figura en la bolsa y quien figura sin ser el creador reciben el mismo 403. Es un tradeoff aceptado: se confirma que la bolsa existe, pero los ids son UUID y no se pueden recorrer probando números.
- Debe existir una ruta para que un invitado vea los términos de la bolsa antes de entrar.
- Saldo insuficiente es 409 porque se decide con el estado de la cuenta, aunque el usuario pueda arreglarlo cargando saldo.

### 2.7 Tiempo y vencimiento

- Una operación sobre una bolsa con `ahora >= fecha_limite` que aún no se liquidó se rechaza con 409 `fuera_de_plazo` y no mueve dinero. Detectarlo no cuesta una consulta extra, porque la bolsa ya está bloqueada y leída.
- Ninguna petición liquida una bolsa. Las peticiones son livianas y un `GET` nunca escribe en el libro.
- La base muestra la bolsa como abierta hasta el siguiente barrido (hasta 60 s), así que el frontend calcula "vencida" con la hora.
- El borde exacto (`>=` o `>`) se confirma en el bloque 6.

### 2.8 Barrido de vencidas

- `procesar_vencidas(ahora)` vive en `services/`. Lista las candidatas sin bloquear y cada paso es una transacción propia que bloquea la bolsa y relee su estado.
- Hace dos trabajos: aplicar la política a las bolsas vencidas sin completar, y retomar las que quedaron a medias.
  - `transferir`: una transacción envía lo reunido a la cuenta objetivo y cierra la bolsa.
  - `devolver`: una transacción por participante con deuda mayor que cero, y al final una que cierra la bolsa con saldo cero.
- Deuda de un participante = aportes menos devoluciones de esa bolsa, calculada desde el libro y **por tipo de transacción**, no por el par de cuentas. La cuenta objetivo puede ser la de un participante, y contar la transferencia final como devolución le restaría de más.
- Si la deuda es mayor que cero se devuelve. Si es cero no se mueve nada. Si fuera negativa es un error que se reporta y no mueve dinero.
- Si una bolsa falla, las demás siguen y la fallida se reintenta en el siguiente ciclo. No hay cola de pendientes: el estado en la base es la cola.
- Repetir el barrido es seguro porque cada paso relee la deuda tras bloquear.

### 2.9 Hilo del barrido

- Es un hilo del mismo proceso de FastAPI, iniciado en el `lifespan` de la aplicación. No es un proceso aparte: comparte memoria y pool de conexiones con la API, y muere con el proceso.
- Un solo bucle: ejecuta el ciclo completo, espera 60 s y repite. Sin solapamiento entre ciclos.
- Condiciones:
  1. Un solo worker de uvicorn. Con varios correrían varios bucles: sería seguro, pero ruidoso.
  2. Sesión propia en cada ciclo, sin estado compartido con las peticiones.
  3. Captura de excepciones por bolsa y por ciclo, con log, para que un error no mate el hilo.
  4. Intervalo en variable de entorno (60 s por defecto) y bandera para apagarlo en las pruebas, que llaman a `procesar_vencidas(ahora)` con hora fija.
  5. El pool tiene capacidad para al menos una conexión del barrido, además de las peticiones.
- Se acepta que si el proceso muere a mitad de un ciclo, la transacción en curso se revierte y las bolsas pendientes esperan al siguiente arranque. Se acepta también el costo de un barrido constante, a cambio de peticiones livianas y de no dejar bolsas eternas.
- Ningún endpoint recibe la hora. Para la demo se crea una bolsa con fecha límite a un par de minutos y se espera al barrido.

### 2.10 Entradas para los bloques siguientes

- **Bloque 3:** tipo de cada transacción (`carga`, `transferencia`, `aporte`, `devolucion`, `transferencia_final` y el envío por decisión), qué guarda la fila de idempotencia cuando la operación no crea una transacción del libro (crear bolsa), y las claves deterministas de las devoluciones del sistema.
- **Bloque 7:** orden de cierre de una cancelación con política `transferir`: primero se devuelven los aportes de quienes decidieron devolver, después se transfiere en una sola operación lo que queda en la bolsa y se cierra. Precondición: ningún participante con una devolución decidida y pendiente. El plazo para decidir y el valor por defecto siguen abiertos.
- **Bloque 9:** si `aportar` no lleva monto (el servidor ya conoce la parte), desaparece la ambigüedad entre 422 y 409 para "pago distinto de la parte exacta".

