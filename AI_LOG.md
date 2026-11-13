# Bitácora de IA

La escribo yo, en el momento en que pasa. Es la base del punto 7 del README: cómo usé la IA y cuándo se equivocó o casi me hizo equivocar.

## Plantilla

### AAAA-MM-DD · Tarea
- **Herramienta:** Claude Code o Kiro.
- **Qué le pedí:**
- **Qué propuso:**
- **Qué decidí yo y por qué:**
- **¿Error o casi error?** Qué fue y cómo me di cuenta (prueba, lectura del diff, auditoría).

### 2026-11-11 · Creación arquitectura para la base de datos
- **Herramienta:** Claude web chat
- **Qué le pedí:** Empezar con el bloque 3 correspondiente al diseño de la base de datos
- **Qué propuso:** Una estructura inicial con varias entidades correctas y que correspondia, pero con mal plateamiento de las relaciones entre las misma y aumento de complejidad innecesaria.
- **Qué decidí yo y por qué:** Decidi dejar relaciones directas, y a la entidad CUENTA como la principal. Asi tambien, establecer todas las tranferencias como transaccion que tienen movimientos asociados.
- **¿Error o casi error?** Complejizar las relaciones entre entidades y que en el futuro me podria haber complicado la implementacion de transacciones. Me di cuenta al analizar su propuesta y ver inconsistencias con lo que tenia plateado anteriormente, que no coincidia con lo discutido con anterioridad.

### 2026-11-12 · Diseño del SPEC: lectura del saldo con bloqueo
- **Herramienta:** Claude (chat, diseño de documentos). Auditoría con otro modelo, en sesión separada.
- **Qué le pedí:** Que diseñara la arquitectura de Cuadre y escribiera el SPEC por bloques, atacando mis respuestas y señalando riesgos con el dinero. Después, que verificara el hallazgo H1 de la auditoría sobre la lectura del saldo.
- **Qué propuso:** En el SPEC 2.4 y 5.1 escribimos "el saldo se lee de la fila ya bloqueada, nunca antes", sin decir cómo. Claude lo confirmó en la documentación de SQLAlchemy 2 y en un reporte de error del proyecto: si la cuenta ya está en la sesión, el `SELECT ... FOR NO KEY UPDATE` deja el objeto con el saldo viejo aunque la fila esté bloqueada. Propuso dos defensas: `populate_existing` en toda lectura con bloqueo, y modificar el saldo solo con `saldo = saldo + :delta` en SQL. También una prueba determinista con dos sesiones.
- **Qué decidí yo y por qué:** Acepté las dos defensas y la prueba, y las dejé en el SPEC (2.4, 10.1 y 10.3), en AGENTS.md (reglas 2 y 6) y en DECISIONS.md. Las dos se complementan: si falla la lectura fresca, el saldo sigue correcto y `ck_cuentas_saldo` impide un saldo negativo.
- **¿Error o casi error?** Casi error de diseño. Escribimos una regla que sonaba segura pero no garantizaba nada. Lo detectó la auditoría con otro modelo (H1), y lo confirmé con la documentación oficial y un reporte de error del propio proyecto. Un escenario de dos transferencias de $60.000 con $100.000 de saldo habría creado $60.000 sin que ninguna invariante lo impidiera de inmediato.

### 2026-11-13 · T1: infraestructura de base y pruebas
- **Herramienta:** Claude Code.
- **Qué le pedí:** Fixtures que crean, vacían y borran cuadre_test, con una guarda que rechaza cualquier base cuyo nombre no termine en _test.
- **Qué propuso:** Pruebas que esperaban RuntimeError cuando la guarda rechaza un nombre.
- **Qué decidí yo y por qué:** Que las pruebas exijan también el mensaje del error, no solo su tipo. Además, que la guarda valide el nombre completo y no solo el sufijo, porque el nombre se pone entre comillas a mano en CREATE y DROP DATABASE.
- **¿Error o casi error?** Casi error. En la fase de pruebas en rojo, las pruebas de la guarda pasaban con las funciones todavía vacías: NotImplementedError hereda de RuntimeError, así que la prueba aceptaba el error equivocado. Lo detectó el propio agente en la primera corrida en rojo y lo corrigió exigiendo el mensaje con match=. Es justo para lo que sirve revisar que las pruebas fallen por la razón correcta.