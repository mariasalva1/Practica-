"""Tests del módulo de apoyo del notebook de análisis (``pong.analisis``)."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import pytest

from pong import analisis
from pong import pong_engine as pe
from pong.analisis import (
    Datos,
    apartado,
    cargar,
    figura_sin_datos,
    filas_vuelo,
    mostrar,
    resolver_partida,
    texto_resumen,
)
from pong.bots_ref import Easy
from pong.registro import guardar_json, jugar_partida

EJEMPLO = Path(__file__).resolve().parents[1] / "notebook" / "ejemplo.json"


def _pendiente(*args):
    raise NotImplementedError


def _roto(*args):
    raise ValueError("fallo de prueba")


def _leer_registro(ruta):
    return {"bots": {"left": "a", "right": "b"}}, pd.DataFrame()


def _identidad(*args):
    return args[0] if args else None


def _html(objeto) -> str:
    return objeto.text


def test_datos_nombre():
    d = Datos(ruta=Path("x.json"), meta={"bots": {"left": "hard", "right": "easy"}})
    assert d.nombre("left") == "hard" and d.nombre("right") == "easy"


def test_filas_vuelo():
    juego = pd.DataFrame({"tick": [10, 11, 12, 13, 20, 21]})
    d = Datos(ruta=Path("x.json"), juego=juego)
    v = pd.Series({"tick_ini": 12, "n_ticks": 3})
    assert filas_vuelo(d, v) == slice(2, 5)


@pytest.mark.parametrize(
    "funciones, texto",
    [
        ((_pendiente, _identidad, _identidad, _identidad), "Pendiente: … L1"),
        ((_leer_registro, _pendiente, _identidad, _identidad), "Pendiente: … L2"),
        ((_leer_registro, _roto, _identidad, _identidad), "Error en L2"),
    ],
)
def test_cargar_anota_lo_pendiente(funciones, texto):
    d = cargar(EJEMPLO, *funciones)
    assert d.pendiente.startswith(texto.replace("…", "completa"))
    assert d.verdad is None


def _tablas_coherentes():
    """Un intercambio de un golpe (2 vuelos), con las columnas pedidas."""
    meta = {
        "semilla": 1,
        "bots": {"left": "a", "right": "b"},
        "sets": {},
        "resultado": "left",
        "abandono": None,
        "tiempo_excedido": None,
    }
    intercambios = pd.DataFrame(
        [[1, 0, 5, 1, "point", "left"]], columns=analisis.COLUMNAS["intercambios"]
    )
    ticks = pd.DataFrame(
        {
            "tick": range(6),
            "state": "playing",
            "ball_x": 400.0,
            "ball_y": 300.0,
            "p_left": 300.0,
            "p_right": 300.0,
            "cmd_left": "STAY",
            "cmd_right": "STAY",
            "server": "left",
            "rally_hits": [0, 0, 0, 1, 1, 1],
        }
    )
    juego = ticks.assign(intercambio=1, nulo=False)
    vuelos = pd.DataFrame(
        [[0, 1, 0, 0, 2, 3, "right", "golpe"], [1, 1, 1, 3, 5, 3, "left", "fallo"]],
        columns=analisis.COLUMNAS["vuelos"],
    )
    return meta, intercambios, ticks, juego, vuelos


def test_comprobar_coherencia_acepta_datos_coherentes():
    analisis.comprobar_coherencia(*_tablas_coherentes())


def _quitar_fila(t):
    t[3] = t[3].drop(index=1).reset_index(drop=True)


def _cambiar_hits(t):
    t[1].loc[0, "hits"] = 2


def _nulo_con_ganador(t):
    t[1].loc[0, "outcome"] = "let"


def _columnas_desordenadas(t):
    t[4] = t[4][["intercambio", "vuelo", *analisis.COLUMNAS["vuelos"][2:]]]


def _sin_clave(t):
    del t[0]["tiempo_excedido"]


def _receptores_iguales(t):
    t[4].loc[1, "receptor"] = "right"


@pytest.mark.parametrize(
    "estropear, texto",
    [
        (_quitar_fila, "ticks no consecutivos"),
        (_cambiar_hits, "número de vuelos"),
        (_nulo_con_ganador, "número de vuelos"),
        (_columnas_desordenadas, "L4: vuelos tiene las columnas"),
        (_sin_clave, "L1: a meta le faltan"),
        (_receptores_iguales, "no se alternan"),
    ],
)
def test_comprobar_coherencia_detecta(estropear, texto):
    tablas = list(_tablas_coherentes())
    estropear(tablas)
    with pytest.raises(AssertionError, match=texto):
        analisis.comprobar_coherencia(*tablas)


def test_cargar_con_funciones_completas(sin_registro, tmp_path):
    ruta = guardar_json(jugar_partida(3, Easy, Easy), tmp_path / "p.json")
    meta, intercambios, ticks, juego, vuelos = _tablas_coherentes()
    d = cargar(
        ruta,
        lambda r: (meta, intercambios),
        lambda r: ticks,
        lambda t, i: juego,
        lambda j: vuelos,
    )
    assert d.pendiente is None
    columnas = ["tick", "ball_vx", "ball_vy", "ball_ay", "ball_speed"]
    assert list(d.verdad.columns) == columnas
    assert "coherentes" in texto_resumen(d)


def test_cargar_se_detiene_si_no_es_coherente(sin_registro, tmp_path):
    ruta = guardar_json(jugar_partida(3, Easy, Easy), tmp_path / "p.json")
    meta, intercambios, ticks, juego, vuelos = _tablas_coherentes()
    d = cargar(
        ruta,
        lambda r: (meta, intercambios),
        lambda r: ticks,
        lambda t, i: juego.drop(index=1).reset_index(drop=True),
        lambda j: vuelos,
    )
    assert d.pendiente.startswith("Los datos de L1–L4 no son coherentes")
    assert "ticks no consecutivos" in d.pendiente
    assert d.verdad is None


def test_cargar_l1_que_no_devuelve_un_par(sin_registro):
    d = cargar(EJEMPLO, lambda r: None, _identidad, _identidad, _identidad)
    assert d.pendiente == "Error en L1: debe devolver (meta, intercambios)"


def test_figura_sin_datos():
    fig = figura_sin_datos("S1")
    assert isinstance(fig, plt.Figure)
    plt.close(fig)


def _figura_buena(d):
    fig, ax = plt.subplots()
    ax.set_title("buena")
    return fig


def figura_pendiente(d):
    raise NotImplementedError


def figura_rota(d):
    raise KeyError("columna")


@pytest.mark.parametrize(
    "funcion, pendiente, aviso",
    [
        (_figura_buena, None, None),
        (figura_pendiente, None, "Pendiente: completa figura_pendiente"),
        (figura_rota, None, "Error en figura_rota"),
        (_figura_buena, "Pendiente: completa L3", "Pendiente: completa L3"),
    ],
)
def test_mostrar(monkeypatch, funcion, pendiente, aviso):
    avisos: list[str] = []
    original = analisis.figura_aviso

    def anotar(texto, color="0.35"):
        avisos.append(texto)
        return original(texto, color)

    monkeypatch.setattr(analisis, "figura_aviso", anotar)
    d = Datos(ruta=Path("x.json"), pendiente=pendiente)
    abiertas = len(plt.get_fignums())
    html = _html(mostrar(funcion, d))
    assert len(plt.get_fignums()) == abiertas  # la figura se cierra
    assert "image/png" in html
    if aviso is None:
        assert avisos == []
    else:
        assert len(avisos) == 1 and avisos[0].startswith(aviso)


def test_apartado():
    d = Datos(ruta=EJEMPLO, pendiente="Pendiente: completa L1")
    assert "Figura S1" in _html(apartado("Figura S1", _figura_buena, d))


@pytest.fixture
def sin_registro(monkeypatch):
    """Sin ``--registro`` en la línea de órdenes (como en el notebook)."""
    monkeypatch.setattr(analisis, "_registro_en_linea_de_ordenes", lambda: None)


def test_resolver_partida_valida(sin_registro, monkeypatch):
    assert resolver_partida(EJEMPLO) == (EJEMPLO, None)
    # Relativa a la raíz del repositorio, desde otra carpeta
    monkeypatch.chdir(EJEMPLO.parents[1] / "tests")
    ruta, motivo = resolver_partida(Path("notebook/ejemplo.json"))
    assert motivo is None and ruta.resolve() == EJEMPLO


def _escribir(tmp_path, nombre, contenido) -> Path:
    ruta = tmp_path / nombre
    ruta.write_text(contenido, encoding="utf-8")
    return ruta


@pytest.mark.parametrize(
    "nombre, contenido, motivo",
    [
        ("no.json", None, "No existe"),
        ("p.csv", "tick\n", "no es un registro JSON"),
        ("p.json", "{roto", "No se puede leer"),
        ("p.json", '{"a": 1}', "no es un registro de partida"),
        (
            "p.json",
            '{"seed": 1, "rallies": [], "commands": "", "engine_version": "0.0"}',
            "es de la versión 0.0",
        ),
    ],
)
def test_resolver_partida_no_valida(sin_registro, tmp_path, nombre, contenido, motivo):
    ruta = tmp_path / nombre
    if contenido is not None:
        _escribir(tmp_path, nombre, contenido)
    assert resolver_partida(ruta)[0] is None
    assert motivo in resolver_partida(ruta)[1]
    d = cargar(ruta, _pendiente, _pendiente, _pendiente, _pendiente)
    assert d.pendiente.startswith("Partida no válida")
    assert "Partida no válida" in texto_resumen(d)


def test_registro_de_la_linea_de_ordenes_sustituye_a_partida(monkeypatch, tmp_path):
    monkeypatch.setattr(analisis, "_registro_en_linea_de_ordenes", lambda: str(EJEMPLO))
    assert resolver_partida(tmp_path / "otra.json") == (EJEMPLO, None)


def test_registro_fuera_de_marimo():
    assert analisis._registro_en_linea_de_ordenes() is None


def test_texto_resumen(sin_registro):
    datos = json.loads(EJEMPLO.read_text(encoding="utf-8"))
    assert datos["engine_version"] == pe.ENGINE_VERSION
    d = Datos(
        ruta=EJEMPLO,
        meta={"semilla": 41, "bots": {"left": "hard", "right": "medium"}},
        ticks=pd.DataFrame({"tick": range(5)}),
        intercambios=pd.DataFrame({"x": range(2)}),
        vuelos=pd.DataFrame({"x": range(3)}),
    )
    texto = texto_resumen(d)
    assert "semilla 41" in texto and "5 ticks" in texto and "coherentes" in texto
