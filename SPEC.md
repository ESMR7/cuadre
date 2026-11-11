# SPEC de Cuadre

> Fuente de verdad del producto. Si `AGENTS.md` y este archivo se contradicen, se detiene el trabajo y se resuelve.
>
> **Estado:** bloque 1 aprobado. Bloques 2 a 11 pendientes.

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
