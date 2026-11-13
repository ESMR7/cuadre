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

### 1. Requisitos

- Docker con Docker Compose v2 y `make`.
- Node.js 24.19.0 (con npm 12.0.2) para el frontend. El frontend usa Angular 22.2.5, fijado en `frontend/package-lock.json`.
- Python 3.12 o superior, solo si quieres correr `make test` en el host.

Configuración inicial:

```bash
cp .env.example .env    # completa POSTGRES_USER, POSTGRES_PASSWORD y POSTGRES_DB,
                        # y usa los mismos valores en DATABASE_URL y TEST_DATABASE_URL
```

### 2. Levantar todo

```bash
make up      # PostgreSQL y la API; la API corre alembic upgrade head al arrancar
make seed    # datos de demo
make front   # instala el frontend con npm ci si hace falta y lo sirve (déjalo corriendo)
```

| Qué | URL |
| --- | --- |
| API | <http://localhost:8000> |
| Documentación interactiva | <http://localhost:8000/docs> (inicia sesión con `POST /sesiones` y usa el token en **Authorize**) |
| Frontend | <http://localhost:4200> |

### 3. Usuarios de demo

`ana`, `beto`, `carla` y `olga`. La contraseña de todos es `demo-cuadre-2026`.

`make seed` hace lo siguiente:

- Carga $200.000 a ana, beto y carla.
- Crea la bolsa `cena`: $90.000 entre ana, beto y carla ($30.000 cada uno), cuenta objetivo olga, vence en 7 días y al vencer envía lo pagado. beto ya aportó.
- Crea la bolsa `vence_pronto`: $20.000 entre beto y carla ($10.000 cada uno), vence 3 minutos después y al vencer devuelve todo. carla ya aportó.

Se puede correr varias veces: lo que ya existe se reporta y no se duplica. Los montos de abajo suponen una base recién sembrada.

### 4. Recorrido manual

Para repetir la demo desde cero: `docker compose down -v`, `make up`, `make seed` (`down -v` borra todos los datos). Los pasos 5 y 7 dependen de una base recién sembrada: con datos de una corrida anterior, los saldos no coinciden, y `vence_pronto` puede haber vencido ya.

En <http://localhost:4200>:

1. **Iniciar sesión como ana.** Entras a *Mi cuenta*. Arriba aparece la alerta rosada **Bolsas que esperan tu acción**: "cena: falta tu aporte de $30.000".
2. **Ver saldo e historial.** El saldo es **$200.000**. El historial muestra una `carga` desde `sistema` por **$200.000**.
3. **Transferir a beto.** En *Transferir*, escribe destino `beto` y monto `20000`. Aparece "Operación realizada.", el saldo baja a **$180.000** y el historial muestra una `transferencia` a beto por **-$20.000**. Si escribes `20.000` o `20000.5`, el formulario rechaza el monto sin enviarlo.
4. **Ver la bolsa cena.** En *Mis bolsas*, abre `cena` (estado ABIERTA, tu estado PENDIENTE). Verás:
   - total $90.000, meta $90.000, aportado $30.000 y transferido —;
   - participantes: 3; pagados: 1; pendientes: 2;
   - tu parte: $30.000;
   - botones *Aportar $30.000*, *Retirarme* y *Cancelar bolsa*. Este último aparece solo porque ana es la creadora.
5. **Aportar como carla.** Sal de la sesión y entra como `carla`.
   - Al entrar, el aviso muestra `cena` (pendiente, $30.000). Si `vence_pronto` no ha vencido, no aparece, porque carla ya pagó esa.
   - Abre `cena` y pulsa *Aportar $30.000*. Antes de enviar, el frontend vuelve a consultar la bolsa y comprueba que la meta no cambió.
   - Resultado: aportado **$60.000**, pagados 2, y el estado de carla pasa a PAGADO.
   - En *Mi cuenta*, el saldo de carla es **$160.000** ($200.000 − $10.000 de `vence_pronto` − $30.000 de `cena`), y el aviso ya no menciona `cena`.
6. **Ver de nuevo el aviso de pendientes.** Entra como ana: el aviso sigue mostrando `cena`, porque ana aún no aporta. Si ana aporta $30.000, todos quedan en `pagado` y en esa misma transacción se transfieren los **$90.000** a olga. La bolsa pasa a CERRADA, con transferido $90.000.
7. **Vencimiento y devolución.** Espera 3 minutos desde `make seed` y corre:

   ```bash
   make vencer
   ```

   `vence_pronto` se liquida. beto (pendiente) pasa a retirado sin movimientos, y carla recibe la devolución de sus **$10.000**. Como carla, su saldo sube a **$170.000** y el historial muestra una `devolucion` desde la bolsa por **$10.000**. La bolsa queda CERRADA.

### 5. Verificación

```bash
make check                                 # invariantes del libro contable (corre dentro del contenedor api)
make test                                  # opcional: suite completa del backend (usa la base cuadre_test)
cd frontend && npx ng test --watch=false   # pruebas unitarias del frontend
```

Para `make test` necesitas el entorno virtual del backend:

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && cd ..
```

Para aplicar las migraciones a mano desde el host: `cd backend && .venv/bin/alembic upgrade head`.

El barrido de vencidas se ejecuta con `make vencer`, no con un hilo automático (recorte 3, `DECISIONS.md`).

### 6. Detener y limpiar

```bash
# Ctrl+C en la terminal de make front para detener el frontend
docker compose down      # detiene la API y la base; los datos se conservan
docker compose down -v   # además borra el volumen: se pierden todos los datos
```
