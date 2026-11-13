# README

> **Proyecto:** Cuadre
> **Autor/a:** Edy Martinez
> **Fecha:** 9 de Noviembre 2026

## Contexto y objetivo

_Describe brevemente qué problema resuelve el sistema, para quién y cuál era el objetivo de esta entrega._

## 01. Decisiones clave y por qué las tomé

### Decisión 1: [Título]

- **Qué decidí:** 
- **Por qué:** 
- **Alternativas consideradas:** 
- **Trade-offs:** 

### Decisión 2: [Título]

- **Qué decidí:** 
- **Por qué:** 
- **Alternativas consideradas:** 
- **Trade-offs:** 

> Repite esta sección para las decisiones más importantes de arquitectura, modelo de datos, interfaz, validaciones, despliegue o proceso.

## 02. Cómo sé que el sistema no pierde un peso

### Qué puede salir mal

- [Riesgo o caso límite 1]
- [Riesgo o caso límite 2]
- [Riesgo o caso límite 3]

### Cómo lo protejo

- [Validación, regla o control que evita el problema]
- [Manejo de errores y casos límite]
- [Auditoría, trazabilidad o mecanismo de recuperación]

### Evidencia de que funciona

- **Pruebas realizadas:** [unitarias, integración, manuales, etc.]
- **Escenarios cubiertos:** 
- **Resultados:** 
- **Limitaciones de la evidencia:** 

_Incluye enlaces a pruebas, capturas, logs o métricas cuando corresponda._

## 03. Qué dejé fuera y por qué

| Fuera de alcance | Motivo | Impacto | Si se retomara, haría |
|---|---|---|---|
| [Funcionalidad o problema] | [Razón] | [Impacto] | [Siguiente paso] |
| [Funcionalidad o problema] | [Razón] | [Impacto] | [Siguiente paso] |

## 04. Qué haría distinto con más tiempo

1. [Mejora o cambio]
2. [Mejora o cambio]
3. [Mejora o cambio]

_Explica por qué cada cambio aumentaría la calidad, seguridad, mantenibilidad o valor del sistema._

## 05. Qué NO sé

- [Pregunta técnica o de negocio que sigue abierta]
- [Comportamiento que no pudiste verificar]
- [Riesgo o dependencia que requiere más investigación]
- [Supuesto que debería validarse con usuarios o datos reales]

## 06. Supuestos que hice y por qué

| Supuesto | Por qué lo hice | Qué pasa si es falso | Cómo lo validaría |
|---|---|---|---|
| [Supuesto] | [Razón] | [Consecuencia] | [Forma de validación] |
| [Supuesto] | [Razón] | [Consecuencia] | [Forma de validación] |

## 07. Cómo usé IA

### Herramientas y dinámica

- **Herramientas utilizadas:** [Herramienta/modelo]
- **Etapas en las que la usé:** [investigación, diseño, implementación, pruebas, documentación]
- **Qué le pedía:** [ejemplos de tareas, sin necesidad de listar todos los prompts]
- **Qué decidía yo:** [criterios, prioridades, trade-offs y validaciones]
- **Cómo verificaba sus respuestas:** [tests, documentación, ejecución, revisión manual]

### Un error o casi-error de la IA

- **Qué sugirió o hizo:** 
- **Por qué parecía razonable:** 
- **Cómo me di cuenta:** 
- **Qué cambié a partir de eso:** 

_La idea es describir la colaboración y el criterio propio, no hacer un log de prompts._

## 08. Qué aprendí

### Algo nuevo para mí

[Describe un concepto, herramienta, técnica o dominio que aprendiste.]

### Algo que me sorprendió

[Describe un resultado inesperado, una dificultad o un supuesto que resultó falso.]

### Qué me llevo

[Resume los aprendizajes que aplicarías en el próximo proyecto.]

## Cómo ejecutar y verificar

### Requisitos

- Docker con Docker Compose v2
- Python 3.12 o superior (solo para correr las pruebas en el host)
- `make`

### Instalación

```bash
cp .env.example .env    # completa POSTGRES_USER, POSTGRES_PASSWORD y POSTGRES_DB,
                        # y usa los mismos valores en DATABASE_URL y TEST_DATABASE_URL
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cd ..
```

### Ejecución

```bash
make up      # levanta PostgreSQL y la API; la API corre alembic upgrade head al arrancar
make seed    # datos de demo: ana, beto, carla y olga
make check   # verifica las invariantes del libro contable
```

- Documentación interactiva: <http://localhost:8000/docs>. Inicia sesión con `POST /sesiones` y usa el token en **Authorize**.
- Contraseña de demo de todos los usuarios: `demo-cuadre-2026`.
- `make seed` crea la bolsa `cena` ($90.000 entre ana, beto y carla, objetivo olga; beto ya aportó) y la bolsa `vence_pronto`, que vence 3 minutos después. Se puede correr varias veces: lo que ya existe se reporta y no se duplica.
- **El barrido de vencidas se ejecuta con `make vencer`**, no con un hilo automático (recorte 3, `DECISIONS.md`). Espera 3 minutos después de `make seed` y corre `make vencer`: carla recibe la devolución de su aporte a `vence_pronto`.
- Para aplicar las migraciones a mano desde el host: `cd backend && .venv/bin/alembic upgrade head`.

### Pruebas

```bash
make test    # usa la base cuadre_test; la crea y la borra sola
```
