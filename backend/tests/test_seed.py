"""Datos de demo (T16): `app.seed` usa solo servicios y se puede repetir."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from app import seed
from app.services import barrido, bolsas, sesiones, usuarios

AHORA = datetime(2026, 11, 13, 15, 0, tzinfo=UTC)


def _correr(bd, ahora: datetime = AHORA) -> int:
    return seed.main(reloj=lambda: ahora, fabrica=bd)


def _saldo(bd, cuenta: str) -> int:
    with bd() as s:
        return s.execute(
            text("SELECT saldo FROM cuentas WHERE id = :c"), {"c": cuenta}
        ).scalar_one()


def _contar(bd, sql: str, **p) -> int:
    with bd() as s:
        return s.execute(text(sql), p).scalar_one()


def _detalle(bd, quien: str, nombre: str):
    with bd() as s:
        token = sesiones.iniciar_sesion(s, quien, seed.CONTRASENA_DEMO, AHORA).token
        for r in bolsas.listar_bolsas(s, token, 0, 100, AHORA):
            if r.nombre == nombre:
                return r
    raise AssertionError(nombre)


def _aportes_de(bd, quien: str) -> int:
    return _contar(
        bd,
        "SELECT count(*) FROM transacciones WHERE tipo = 'aporte' AND cuenta_origen_id = :q",
        q=quien,
    )


def test_seed_crea_usuarios_bolsas_y_aporte(bd, capsys):
    assert _correr(bd) == 0
    assert _saldo(bd, "ana") == 200_000
    assert _saldo(bd, "beto") == 170_000
    assert _saldo(bd, "carla") == 190_000
    assert _saldo(bd, "olga") == 0
    cena = _detalle(bd, "beto", "cena")
    assert (cena.estado, cena.mi_parte, cena.mi_estado) == ("abierta", 30_000, "pagado")
    assert _detalle(bd, "ana", "cena").mi_estado == "pendiente"
    vence = _detalle(bd, "carla", "vence_pronto")
    assert vence.fecha_limite == AHORA + timedelta(minutes=3)
    assert vence.mi_estado == "pagado"
    salida = capsys.readouterr().out
    for secreto in (*seed.USUARIOS.values(), seed.CONTRASENA_DEMO):
        assert secreto not in salida


def test_seed_dos_veces_no_duplica_movimientos(bd, capsys):
    assert _correr(bd) == 0
    movimientos = _contar(bd, "SELECT count(*) FROM movimientos")
    capsys.readouterr()
    assert _correr(bd) == 0
    assert _contar(bd, "SELECT count(*) FROM movimientos") == movimientos
    assert _saldo(bd, "beto") == 170_000
    assert "ya existían" in capsys.readouterr().out


def test_seed_completa_un_estado_parcial(bd):
    with bd() as s:
        usuarios.registrar(s, "ana", "1000000001", seed.CONTRASENA_DEMO, AHORA)
    assert _correr(bd) == 0
    assert _saldo(bd, "carla") == 190_000
    assert _detalle(bd, "beto", "cena").mi_estado == "pagado"


def test_seed_completa_la_cena_sin_el_aporte_de_beto(bd):
    with bd() as s:
        for nombre, cedula in seed.USUARIOS.items():
            usuarios.registrar(s, nombre, cedula, seed.CONTRASENA_DEMO, AHORA)
        token = sesiones.iniciar_sesion(s, "ana", seed.CONTRASENA_DEMO, AHORA).token
        bolsas.crear_bolsa(
            s,
            token,
            "cena",
            90_000,
            ["ana", "beto", "carla"],
            "olga",
            AHORA + timedelta(days=7),
            True,
            AHORA,
        )
    assert _correr(bd) == 0
    assert _detalle(bd, "beto", "cena").mi_estado == "pagado"
    assert _aportes_de(bd, "beto") == 1


def test_seed_repetido_tras_vencer_vence_pronto_no_falla(bd):
    assert _correr(bd) == 0
    barrido.procesar_vencidas(bd, AHORA + timedelta(minutes=4))
    assert _correr(bd, AHORA + timedelta(minutes=5)) == 0
    assert _aportes_de(bd, "carla") == 1
    assert _saldo(bd, "carla") == 200_000


def test_seed_vence_pronto_se_devuelve_con_el_barrido(bd):
    assert _correr(bd) == 0
    barrido.procesar_vencidas(bd, AHORA + timedelta(minutes=4))
    assert _saldo(bd, "carla") == 200_000
    assert (
        _contar(bd, "SELECT count(*) FROM transacciones WHERE tipo = 'devolucion'") == 1
    )


def test_seed_ante_error_inesperado_solo_muestra_el_tipo(bd, capsys):
    def reloj_roto():
        raise RuntimeError("secreto-que-no-debe-salir")

    assert seed.main(reloj=reloj_roto, fabrica=bd) == 2
    salida = capsys.readouterr()
    assert "RuntimeError" in salida.out
    assert "secreto" not in salida.out + salida.err
