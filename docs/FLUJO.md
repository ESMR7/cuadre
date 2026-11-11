# Cómo trabajo con los agentes en Cuadre

## Qué archivo lee cada herramienta

| Archivo | Para qué | Quién lo lee |
| --- | --- | --- |
| `AGENTS.md` | Reglas del dinero, protocolo de trabajo y convenciones. Única fuente de reglas | Kiro automáticamente; Claude Code a través de `CLAUDE.md` |
| `CLAUDE.md` | Importa `AGENTS.md` y agrega lo propio de Claude Code | Claude Code |
| `.claude/commands/` | Atajos `/planear`, `/pruebas`, `/implementar` y `/auditar` | Claude Code |
| `.claude/settings.json` | Impide que Claude Code lea `.env` | Claude Code |
| `DECISIONS.md` y `AI_LOG.md` | Bitácoras para el README | Yo |

Si una regla cambia, se cambia solo en `AGENTS.md`.

## El ciclo de cada tarea

1. **Elige una tarea pequeña** del roadmap: una parte de una fase, no la fase entera.
2. **Empieza con contexto limpio:** `/clear` en Claude Code o una sesión nueva en Kiro.
3. **Pide el plan.** En Claude Code: `/planear <tarea>`, o activa el modo plan con Shift+Tab. En Kiro: `PLAN: <tarea>`.
4. **Revisa el plan:** ¿las pruebas cubren casos borde y errores? ¿Respeta las reglas del dinero? ¿Toca archivos fuera del alcance? Responde `CAMBIOS: ...` o `APROBADO`.
5. **Revisa las pruebas en rojo.** Es tu control de calidad más importante: si una prueba verifica lo incorrecto, el código pasará y estará mal. Luego `/implementar` en Claude Code o `SIGUE` en Kiro.
6. **Déjalo trabajar, pero vigila.** Si se desvía, interrúmpelo (Esc en Claude Code) y corrige.
7. **Lee el diff completo** con `git diff`. Si no entiendes algo, pide que te lo explique antes de aceptarlo.
8. **Corre tú mismo `pytest`** una vez.
9. **Haz commit** pequeño con el mensaje sugerido.
10. **Anota en `DECISIONS.md` y `AI_LOG.md`**, con tus palabras, en el momento.

## Claude Code y Kiro juntos

- Solo un agente escribe en el repo a la vez. Nunca los pongas a editar los mismos archivos en paralelo.
- Propuesta: Claude Code construye y Kiro audita en una sesión aparte con `AUDITA: último cambio`. Una revisión con otro contexto encuentra errores que la sesión original no ve.
- Al abrir una sesión de Kiro, pide: "Resume en cinco líneas las reglas del dinero de AGENTS.md". Así confirmas que las cargó.

## Higiene de contexto

- `/clear` entre tareas y `/compact` si una sesión se alarga.
- Si el agente repite un error, agrega la regla a `AGENTS.md`.
- Haz commit después de cada tarea en verde: es tu punto seguro para volver atrás.

## Señales para detenerlo de inmediato

- Propone `float`, quitar un bloqueo o relajar una restricción.
- Modifica, salta o debilita una prueba aprobada.
- Agrega una dependencia o toca archivos fuera del plan.
- Intenta leer `.env` o ejecutar algo destructivo.
- Dice que "simplificó" algo en el manejo del dinero sin habértelo consultado.

## Qué es solo mío

El `README.md`, el `AI_LOG.md`, el video y las decisiones finales. Los agentes pueden proponer, pero yo escribo y decido.
