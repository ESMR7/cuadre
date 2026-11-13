# Comandos del proyecto, desde la raíz. PYTHON es relativo a backend/;
# en integración continua: make test PYTHON=python
PYTHON ?= .venv/bin/python

.PHONY: up test check vencer

up:
	docker compose up -d db

test:
	cd backend && $(PYTHON) -m pytest

check:
	cd backend && $(PYTHON) -m app.db.invariantes

vencer:
	cd backend && $(PYTHON) -m app.vencer
