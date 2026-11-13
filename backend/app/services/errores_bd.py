"""Ayudas para interpretar errores de PostgreSQL en los servicios."""

from sqlalchemy.exc import IntegrityError


def nombre_restriccion(error: IntegrityError) -> str | None:
    """Nombre de la restricción violada, leído del diagnóstico de psycopg."""
    diagnostico = getattr(error.orig, "diag", None)
    return getattr(diagnostico, "constraint_name", None)
