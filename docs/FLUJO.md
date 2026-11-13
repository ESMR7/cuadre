# Cómo trabajo con los agentes en Cuadre

## Qué archivo lee cada herramienta

| Archivo | Para qué | Quién lo lee |
| --- | --- | --- |
| `SPEC.md` | Fuente de verdad del producto: modelo, reglas, estados, API y pruebas | Los agentes al planear cada tarea; yo al revisar |
| `AGENTS.md` | Reglas del dinero, protocolo de trabajo y convenciones. Única fuente de reglas | Kiro automáticamente; Claude Code a través de `CLAUDE.md` |
| `CLAUDE.md` | Importa `AGENTS.md` y agrega lo propio de Claude Code | Claude Code |
| `docs/Roadmap del reto técnico HabiCapital.md` | Lista de tareas (T1 a T17), con las secciones del SPEC de cada una y su tiempo | Yo, para elegir la siguiente tarea |
| `.claude/commands/` | Atajos `/planear`, `/pruebas`, `/implementar` y `/auditar` | Claude Code |
| `.claude/settings.json` | Impide que Claude Code lea `.env` | Claude Code |
| `DECISIONS.md` y `AI_LOG.md` | Bitácoras para el README | Yo |

Si una regla cambia, se cambia en `AGENTS.md`. Si cambia el producto, se cambia en `SPEC.md`. Si los dos se contradicen, el agente se detiene y pregunta.

## El ciclo de cada tarea

1. **Toma la siguiente tarea del roadmap** (T1, T2...). Ya están dimensionadas; no juntes dos ni partas una sin anotarlo.
2. **Empieza con contexto limpio:** `/clear` en Claude Code o una sesión nueva en Kiro.
3. **Pide el plan** nombrando la tarea y sus secciones del SPEC. En Claude Code: `/planear T6 del roadmap: libro, cargar y transferir. Lee SPEC 2.3 a 2.5 y 5.4 a 5.6.` En Kiro: `PLAN: ...` con el mismo texto.
4. **Revisa el plan:** ¿las pruebas cubren casos borde y errores? ¿Respeta las reglas del dinero? ¿Toca archivos fuera del alcance? Responde `CAMBIOS: ...` o `APROBADO`. En las tareas que no mueven dinero (T1 a T5, T8 a T10, T15 y T16) puedes responder `APROBADO sin pausa` para ahorrar la parada entre pruebas e implementación.
5. **Revisa las pruebas en rojo** en las tareas que mueven dinero (T6, T7, T11 a T14). Es tu control de calidad más importante: si una prueba verifica lo incorrecto, el código pasará y estará mal. Luego `/implementar` en Claude Code o `SIGUE` en Kiro.
6. **Déjalo trabajar, pero vigila.** Si se desvía, interrúmpelo (Esc en Claude Code) y corrige.
7. **Lee el diff completo** con `git diff`. Si no entiendes algo, pide que te lo explique antes de aceptarlo.
8. **Corre tú mismo `pytest` y `make check`** (desde T3) una vez.
9. **Haz commit** pequeño con el mensaje sugerido.
10. **Anota en `DECISIONS.md` y `AI_LOG.md`**, con tus palabras, en el momento. Si no hubo decisión ni error, no anotes nada.
11. **Mira el reloj** contra los puntos de control del roadmap. Si una tarea pasa en más de la mitad su tiempo, detente y decide: seguir, simplificar o aplicar el recorte que corresponda.

## Claude Code y Kiro juntos

- Solo un agente escribe en el repo a la vez. Nunca los pongas a editar los mismos archivos en paralelo.
- Claude Code construye. Kiro audita en una sesión aparte, solo después de T6, T11 y T14, con `AUDITA: último cambio`. Atiende solo los hallazgos de gravedad alta; los demás se anotan para el README.
- Al abrir una sesión de Kiro, pide: "Resume en cinco líneas las reglas del dinero de AGENTS.md". Así confirmas que las cargó.

## Formato de AI_LOG.md

```markdown
### AAAA-MM-DD · Tarea
- **Herramienta:** Claude Code o Kiro.
- **Qué le pedí:**
- **Qué propuso:**
- **Qué decidí yo y por qué:**
- **¿Error o casi error?** Qué fue y cómo me di cuenta (prueba, lectura del diff, auditoría).
```

## Higiene de contexto

- `/clear` entre tareas y `/compact` si una sesión se alarga.
- Si el agente repite un error, agrega la regla a `AGENTS.md`.
- Haz commit después de cada tarea en verde: es tu punto seguro para volver atrás.

## Señales para detenerlo de inmediato

- Propone `float`, quitar un bloqueo o relajar una restricción.
- Bloquea las cuentas con `FOR UPDATE` en vez de `with_for_update(key_share=True)`, olvida `populate_existing` o calcula el saldo en Python y lo escribe.
- Valida un patrón con `re.match` en vez de `re.fullmatch` o el `pattern` de Pydantic.
- Modifica, salta o debilita una prueba aprobada.
- Agrega una dependencia o toca archivos fuera del plan.
- Implementa algo que `SPEC.md` declara fuera de alcance.
- Intenta leer `.env` o ejecutar algo destructivo.
- Dice que "simplificó" algo en el manejo del dinero sin habértelo consultado.

## Qué es solo mío

El `README.md`, el `AI_LOG.md`, el video, los recortes y las decisiones finales. Los agentes pueden proponer, pero yo escribo y decido.
