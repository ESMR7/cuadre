"""Modelos de la base. Las tablas llegan en T2."""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# SPEC 3.1: toda restricción tiene nombre con prefijo pk_, ck_, uq_, fk_ o ix_.
CONVENCION_NOMBRES = {
    "pk": "pk_%(table_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENCION_NOMBRES)
