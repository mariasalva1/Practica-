"""Tests de forma del notebook de análisis (``notebook/analisis_mo.py``).

Son de la plantilla, no cuentan como tus tests. Comprueban que el notebook
conserva las funciones con los nombres y parámetros pedidos (el profesor las
corrige con tests propios) y que se ejecuta entero con la partida de ejemplo.
No comprueban que tus funciones sean correctas.
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import sys
from pathlib import Path

import pytest

NOTEBOOK = Path(__file__).resolve().parents[1] / "notebook"

# Funciones que escribe el alumno: nombre → parámetros, en orden.
FIRMAS: dict[str, list[str]] = {
    "leer_registro": ["ruta"],
    "leer_ticks": ["ruta"],
    "limpiar": ["ticks", "intercambios"],
    "vuelos": ["juego"],
    "v0_y_a": ["y"],
    "ticks_validos": ["y0", "v0", "a", "n_obs"],
    "residuos_p1": ["d"],
    "figura_p1": ["d"],
    "plegar": ["Y"],
    "desplegar": ["y"],
    "ajuste_mc": ["Y"],
    "comprobar_p2": ["d"],
    "figura_p2": ["d"],
    "cruce": ["x0", "vx", "X"],
    "ordenada_impacto": ["y0", "v0", "a", "n", "tau"],
    "comprobar_p3": ["d"],
    "figura_p3": ["d"],
    "velocidades": ["d"],
    "estimar_ultimas": ["y"],
    "error_estimacion": ["d"],
    "figura_p4": ["d"],
    "intervalo_wilson": ["k", "n", "z"],
    "golpes": ["d"],
    "figura_s1": ["d"],
    "figura_s2": ["d"],
    "figura_s3": ["d"],
    "figura_s4": ["d"],
    "tasa_fallos": ["d", "clases"],
    "figura_s5": ["d"],
    "ventaja_saque": ["d"],
    "figura_s6": ["d"],
    "recorrido": ["d"],
    "figura_s7": ["d"],
    "marcador": ["d"],
    "figura_s8": ["d"],
}
FIGURAS = ("p1", "p2", "p3", "p4", "s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8")


@pytest.fixture(scope="module")
def nb():
    """El notebook importado como módulo."""
    spec = importlib.util.spec_from_file_location(
        "analisis_mo", NOTEBOOK / "analisis_mo.py"
    )
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["analisis_mo"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


@pytest.mark.parametrize("nombre", sorted(FIRMAS))
def test_funcion_con_la_firma_pedida(nb, nombre):
    assert hasattr(nb, nombre), f"falta la función {nombre}"
    parametros = list(inspect.signature(getattr(nb, nombre)).parameters)
    assert parametros == FIRMAS[nombre], f"{nombre}{tuple(parametros)}"


def test_partida_de_ejemplo_y_notebook_de_ejemplo():
    datos = json.loads((NOTEBOOK / "ejemplo.json").read_text(encoding="utf-8"))
    assert datos["seed"] == 41 and datos["bots"] == {"left": "hard", "right": "medium"}
    html = (NOTEBOOK / "ejemplo.html").read_text(encoding="utf-8")
    for nombre in FIGURAS:
        assert f"Figura {nombre.upper()}" in html, nombre
    assert html.count("data:image/png;base64,") == len(FIGURAS)


PARTIDAS_REQUISITO = [
    "ejemplo.json",
    "raras/abandono.json",
    "raras/nulo.json",
    "raras/tiempo.json",
]


@pytest.mark.parametrize("partida", PARTIDAS_REQUISITO)
def test_requisito_L1_L4_cargan_cualquier_partida(nb, partida, monkeypatch):
    """Requisito del notebook: tus L1–L4 cargan cualquier partida.

    Si este test falla, el notebook se califica con 0 (README, apartado 3). Se
    salta mientras L1–L4 estén por hacer.
    """
    from pong import analisis

    monkeypatch.setattr(analisis, "_registro_en_linea_de_ordenes", lambda: None)
    d = analisis.cargar(
        NOTEBOOK / partida, nb.leer_registro, nb.leer_ticks, nb.limpiar, nb.vuelos
    )
    if d.pendiente is not None and d.pendiente.startswith("Pendiente: completa"):
        pytest.skip(f"{d.pendiente} (L1–L4 por hacer)")
    assert d.pendiente is None, d.pendiente


def test_el_notebook_se_ejecuta_entero(nb, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["analisis_mo.py"])
    _, definiciones = nb.app.run()
    d = definiciones["d"]
    assert d.ruta.name == "ejemplo.json"
