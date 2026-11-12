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