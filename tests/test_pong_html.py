"""Tests de la capa Python de pong.html, ejecutada aquí con CPython.

La página ejecuta en Pyodide el mismo código Python que estos tests extraen
de ``pong.html``. La prueba en un navegador real está en
``.github/pruebas/test_pong_html_navegador.py`` y solo se ejecuta en la CI
de la plantilla.
"""

from __future__ import annotations

import json
import re
import sys
import time
import types
from pathlib import Path

import pytest

from pong import pong_engine as pe
from pong import registro
from pong.bots_ref import Easy
from pong.registro import guardar_json, jugar_partida

RAIZ = Path(__file__).resolve().parents[1]
PAGINA = RAIZ / "pong.html"


def _modulo_pagina() -> types.ModuleType:
    html = PAGINA.read_text(encoding="utf-8")
    m = re.search(
        r'<script type="text/x-python" id="pong-web-py">\n(.*?)</script>', html, re.S
    )
    assert m, "pong.html no contiene el módulo pong_web"
    modulo = types.ModuleType("pong_web")
    sys.modules["pong_web"] = modulo
    exec(compile(m.group(1), "pong.html:pong_web", "exec"), modulo.__dict__)
    return modulo


pw = _modulo_pagina()


class Dibujante:
    """Sigue la bola, imprime, falla y devuelve valores no válidos a propósito."""

    def __init__(self, seed: int) -> None:
        self.n = 0
        self.depuracion: dict = {}

    def decide(self, state: dict) -> str:
        self.n += 1
        if self.n % 300 == 0:
            print("tick", state["tick"])
        if self.n % 500 == 0:
            raise ValueError("fallo de prueba")
        if self.n % 700 == 0:
            return "up"
        y = state["ball_y"]
        self.depuracion = {
            "objetivo_y": y,
            "trayectoria": [(state["ball_x"], y), (30, y)],
            "texto": f"n = {self.n}",
            "otra_clave": object(),
        }
        d = y - state["my_paddle_y"]
        return "DOWN" if d > 4 else "UP" if d < -4 else "STAY"


class Roto:
    def __init__(self, seed: int) -> None:
        raise RuntimeError("constructor roto")

    def decide(self, state: dict) -> str:
        return "STAY"


def _jugar_entera(sesion) -> None:
    while not sesion.terminada:
        sesion.avanzar(5000)


def _registro_cpython(seed, izq, der, nombres, tmp_path: Path) -> str:
    partida = jugar_partida(seed, izq, der, nombres)
    return guardar_json(partida, tmp_path / "cpython.json").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# La página usa el motor y el registro sin cambios
# ---------------------------------------------------------------------------


def test_ficheros_que_lee_la_pagina_existen():
    html = PAGINA.read_text(encoding="utf-8")
    rutas = re.findall(r'"(src/pong/[\w/]+\.py)"', html)
    assert {"src/pong/pong_engine.py", "src/pong/bot.py"} <= set(rutas)
    for ruta in rutas:
        assert (RAIZ / ruta).is_file(), ruta


def test_pyodide_fijado_en_la_serie_de_python_3_13():
    html = PAGINA.read_text(encoding="utf-8")
    versiones = set(re.findall(r"pyodide/v([\d.]+)/full/", html))
    assert len(versiones) == 1
    # Pyodide 0.29.x es la última serie con Python 3.13
    assert versiones.pop().startswith("0.29.")


def test_directo_da_el_mismo_registro_que_jugar_partida(tmp_path, capsys):
    sesion = pw.nueva_directo(11, "dibujante", Dibujante, "easy", Easy)
    _jugar_entera(sesion)
    esperado = _registro_cpython(11, Dibujante, Easy, ("dibujante", "easy"), tmp_path)
    assert sesion.json_registro() == esperado


def test_directo_guarda_prints_excepciones_y_avisos():
    sesion = pw.nueva_directo(3, "dibujante", Dibujante, "easy", Easy)
    sesion.avanzar(1500)
    tipos = [m["tipo"] for m in json.loads(sesion.mensajes_desde(0))]
    assert tipos.count("print") == 5
    assert tipos.count("error") == 3
    assert tipos.count("aviso") == 2
    errores = [m for m in sesion.mensajes if m["tipo"] == "error"]
    assert all("ValueError: fallo de prueba" in m["texto"] for m in errores)
    assert {m["lado"] for m in sesion.mensajes} == {"left"}


def test_depuracion_se_filtra_y_se_guarda_por_tick():
    sesion = pw.nueva_directo(3, "dibujante", Dibujante, "easy", Easy)
    sesion.avanzar(100)
    f = sesion.fotograma(50)
    dep = json.loads(f["depuracion"][0])
    assert set(dep) == {"objetivo_y", "trayectoria", "texto"}
    assert dep["texto"] == "n = 51"
    assert f["depuracion"][1] is None


def test_leer_depuracion_ignora_valores_no_validos():
    bot = types.SimpleNamespace(
        depuracion={
            "objetivo_y": float("nan"),
            "trayectoria": [(1, 2), ("a", 3), (4,), (5, 6)],
            "puntos": "no es una lista",
        }
    )
    assert json.loads(pw.leer_depuracion(bot)) == {
        "trayectoria": [[1.0, 2.0], [5.0, 6.0]],
        "puntos": [],
    }
    assert pw.leer_depuracion(types.SimpleNamespace()) is None
    assert pw.leer_depuracion(types.SimpleNamespace(depuracion=[1, 2])) is None


def test_constructor_que_falla_pierde_sin_jugar(tmp_path):
    sesion = pw.nueva_directo(5, "easy", Easy, "roto", Roto)
    assert sesion.terminada
    resumen = json.loads(sesion.resumen())
    assert resumen["abandono"] == "right" and resumen["resultado"] == "left"
    assert "constructor roto" in sesion.mensajes[0]["texto"]
    assert sesion.json_registro() == _registro_cpython(
        5, Easy, Roto, ("easy", "roto"), tmp_path
    )


def test_estado_bot_es_el_de_state_for():
    sesion = pw.nueva_directo(9, "easy", Easy, "easy2", Easy)
    match = pe.Match(9)
    bots = (Easy(19), Easy(20))
    for i in range(400):
        for lado in (pe.LEFT, pe.RIGHT):
            assert json.loads(sesion.estado_bot(i, lado)) == match.state_for(lado)
        sesion.avanzar(1)
        match.step(*(b.decide(match.state_for(k)) for k, b in enumerate(bots)))


# ---------------------------------------------------------------------------
# Reproducción
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def registro_easy(tmp_path_factory) -> str:
    partida = jugar_partida(21, Easy, Dibujante, ("easy", "dibujante"))
    ruta = tmp_path_factory.mktemp("registro") / "partida_21.json"
    return guardar_json(partida, ruta).read_text(encoding="utf-8")


def test_reproduccion_verificada(registro_easy):
    sesion = pw.Sesion.reproduccion(registro_easy)
    assert sesion.verificacion == {
        "ok": True,
        "problemas": [],
        "tiempo_excedido": None,
    }
    assert sesion.total() == json.loads(sesion.resumen())["tick"] + 1


@pytest.mark.parametrize(
    "cambio, texto",
    [
        (
            lambda d: d["rallies"][1].update(hits=d["rallies"][1]["hits"] + 1),
            "El intercambio 2",
        ),
        (lambda d: d.update(sets={"left": 9, "right": 9}), "Sets"),
        (lambda d: d.update(commands=d["commands"] + "4"), "termina en el tick"),
        (lambda d: d.update(commands=d["commands"][:-1]), "no terminan la partida"),
        (lambda d: d.update(engine_version="0.9"), "versión 0.9"),
    ],
)
def test_reproduccion_detecta_registros_que_no_coinciden(registro_easy, cambio, texto):
    datos = json.loads(registro_easy)
    cambio(datos)
    v = pw.Sesion.reproduccion(json.dumps(datos)).verificacion
    assert not v["ok"]
    assert any(texto in p for p in v["problemas"]), v["problemas"]


class Lento(Easy):
    def decide(self, state: dict) -> str:
        time.sleep(0.003)
        return super().decide(state)


def test_reproduccion_de_partida_cortada_por_tiempo(monkeypatch, tmp_path):
    monkeypatch.setattr(registro, "LLAMADAS_CORTE", 20)
    partida = jugar_partida(5, Lento, Easy, ("lento", "easy"), limite_media_ms=2.0)
    texto = guardar_json(partida, tmp_path / "p.json").read_text(encoding="utf-8")
    sesion = pw.Sesion.reproduccion(texto)
    v = sesion.verificacion
    assert v["ok"] and v["tiempo_excedido"] == "left", v
    resumen = json.loads(sesion.resumen())
    assert resumen["terminada"] and resumen["resultado"] == "right"
    # Quitar la marca: los comandos ya no terminan la partida
    datos = json.loads(texto)
    datos["tiempo_excedido"] = None
    v = pw.Sesion.reproduccion(json.dumps(datos)).verificacion
    assert not v["ok"]


def test_buscar_evento_encuentra_golpes_y_puntos(registro_easy):
    sesion = pw.Sesion.reproduccion(registro_easy)
    i = 0
    eventos = 0
    while (j := sesion.buscar_evento(i)) is not None:
        assert j > i
        i = j
        eventos += 1
    rallies = json.loads(registro_easy)["rallies"]
    golpes = sum(r["hits"] for r in rallies)
    # Cada golpe y cada final de intercambio es un evento (el último, el final)
    assert eventos >= golpes + len(rallies) - 1
    assert i == sesion.total() - 1
