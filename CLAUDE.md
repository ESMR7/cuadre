@AGENTS.md

## Específico de Claude Code

- Las reglas y el protocolo están en AGENTS.md, importado arriba. Es la única fuente: no dupliques reglas aquí.
- Fase 1: si estás en modo plan, presenta el plan con el formato de la Fase 1 y espera aprobación. Fuera del modo plan aplica igual: no edites archivos hasta recibir `APROBADO`.
- Comandos del proyecto en `.claude/commands/`: `/planear <tarea>`, `/pruebas`, `/implementar` y `/auditar <alcance>`.
- Usa una lista de tareas para seguir los pasos del plan aprobado y márcalos al terminarlos.
- Si la conversación acumula trabajo de una tarea anterior, sugiere al usuario empezar con `/clear` antes de planear la siguiente.
