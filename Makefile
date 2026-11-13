# Comandos del proyecto, desde la raíz. make test corre en el host (PYTHON es
# relativo a backend/); seed, check y vencer corren dentro del contenedor api.
# En integración continua: make test PYTHON=python
PYTHON ?= .venv/bin/python

.PHONY: up test check vencer seed front

up:
	docker compose up -d --build

test:
	cd backend && $(PYTHON) -m pytest

check:
	docker compose exec api python -m app.db.invariantes

vencer:
	docker compose exec api python -m app.vencer

seed:
	docker compose exec api python -m app.seed

# Servidor de desarrollo del frontend en http://localhost:4200 (instala si falta node_modules).
front:
	cd frontend && { [ -d node_modules ] || npm ci; } && npx ng serve --port 4200
