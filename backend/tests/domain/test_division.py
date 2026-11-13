"""División exacta de una bolsa (SPEC 1.5, 3.7 y 6.3)."""

from hypothesis import given
from hypothesis import strategies as st

from app.domain.bolsas import dividir
from app.domain.constantes import (
    MARGEN_TOTAL,
    MAX_PARTICIPANTES,
    MIN_PARTICIPANTES,
    TOPE_OPERACION,
    TOTAL_MINIMO,
)


@st.composite
def bolsas(draw: st.DrawFn) -> tuple[int, list[str], str]:
    """N entre 2 y 50 y total entre $10.000 y N × $49.990.000 (SPEC 1.5)."""
    n = draw(st.integers(MIN_PARTICIPANTES, MAX_PARTICIPANTES))
    total = draw(st.integers(TOTAL_MINIMO, n * (TOPE_OPERACION - MARGEN_TOTAL)))
    participantes = [f"u{i}" for i in range(n)]
    creador = draw(st.sampled_from(participantes))
    return total, participantes, creador


@given(bolsas())
def test_suma_de_partes_igual_al_total(datos):
    total, participantes, creador = datos
    partes = dividir(total, participantes, creador)
    assert sum(partes.values()) == total
    assert set(partes) == set(participantes)
    assert all(type(p) is int for p in partes.values())


@given(bolsas())
def test_toda_parte_mayor_que_cero(datos):
    total, participantes, creador = datos
    assert all(p > 0 for p in dividir(total, participantes, creador).values())


@given(bolsas())
def test_ninguna_parte_menor_que_la_base(datos):
    total, participantes, creador = datos
    base = total // len(participantes)
    assert all(p >= base for p in dividir(total, participantes, creador).values())


@given(bolsas())
def test_creador_supera_a_los_demas_en_maximo_49(datos):
    total, participantes, creador = datos
    partes = dividir(total, participantes, creador)
    base = total // len(participantes)
    assert 0 <= partes[creador] - base <= 49
    assert all(p == base for u, p in partes.items() if u != creador)


@given(bolsas())
def test_ninguna_parte_pasa_el_tope(datos):
    total, participantes, creador = datos
    partes = dividir(total, participantes, creador)
    assert all(p <= TOPE_OPERACION for p in partes.values())


@given(bolsas())
def test_division_es_determinista(datos):
    total, participantes, creador = datos
    assert dividir(total, participantes, creador) == dividir(
        total, list(participantes), creador
    )


def test_division_90000_entre_tres():
    partes = dividir(90_000, ["ana", "beto", "carla"], "ana")
    assert partes == {"ana": 30_000, "beto": 30_000, "carla": 30_000}


def test_division_con_resto_maximo():
    """10.049 entre 50: base 200 y resto 49, que paga el creador."""
    participantes = [f"u{i:02d}" for i in range(50)]
    partes = dividir(10_049, participantes, "u07")
    assert partes["u07"] == 249
    assert all(partes[u] == 200 for u in participantes if u != "u07")
    assert sum(partes.values()) == 10_049
