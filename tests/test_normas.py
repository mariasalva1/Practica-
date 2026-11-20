"""Tests de las normas del bot (``pong.normas``).

``test_tu_bot_cumple_las_normas`` revisa tu ``src/pong/bot.py``: si falla,
``runner`` y ``evaluate`` tampoco jugarán con tu bot.
"""

from __future__ import annotations

import pytest

from pong import normas, runner
from pong.bots_ref import Easy
from pong.normas import comprobar_bot, comprobar_clase, infracciones


def test_tu_bot_cumple_las_normas():
    assert comprobar_bot() == []


BUENO = '''
"""Bot con todo lo permitido."""
from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass

import numpy as np


@dataclass
class Punto:
    x: float
    y: float

    def __eq__(self, otro):
        return (self.x, self.y) == (otro.x, otro.y)


class Bot:
    def __init__(self, seed: int) -> None:
        self._azar = random.Random(seed)
        self._historial = deque(maxlen=3)

    def decide(self, state: dict) -> str:
        self._historial.append(state["ball_y"])
        y = float(np.mean(self._historial)) + math.sqrt(4.0)
        return "DOWN" if y > state["my_paddle_y"] else "UP"


if __name__ == "__main__":
    print(Bot(1).decide({"ball_y": 1.0, "my_paddle_y": 0.0}))
'''


def test_un_bot_normal_cumple():
    assert infracciones(BUENO) == []


@pytest.mark.parametrize(
    "codigo, texto",
    [
        ("from pong_ref_bots import Hard as Bot", "importa pong_ref_bots"),
        ("import pong_ref_bots", "importa pong_ref_bots"),
        ("from pong_ref_bots._bots import Hard", "importa pong_ref_bots._bots"),
        ("from pong.bots_ref import Easy", "importa pong.bots_ref"),
        ("from pong import pong_engine", "importa pong"),
        ("from . import bots_ref", "importación relativa"),
        ("import os", "importa os"),
        ("import importlib", "importa importlib"),
        ("m = __import__('pong_ref_bots')", "usa __import__"),
        ("exec('from pong_ref_bots import Hard')", "usa exec"),
        ("import dataclasses\nm = dataclasses.sys.modules", "usa .sys"),
        ("import random\no = random._os", "usa ._os"),
        ("c = object.__subclasses__()", "usa .__subclasses__"),
        ("f = getattr(object, 'x')", "usa getattr"),
        ("import numpy as np\nnp.save('x.npy', 1)", "usa .save"),
        ("from numpy import load", "importa load"),
        ("f = open('datos.txt')", "usa open"),
        ("b = __builtins__", "usa __builtins__"),
        ("def (", "error de sintaxis"),
    ],
)
def test_detecta_infracciones(codigo, texto):
    mensajes = infracciones(codigo)
    assert mensajes, codigo
    assert any(texto in m for m in mensajes), mensajes
    assert mensajes[0].startswith("línea ")


def test_infracciones_ordenadas_por_linea():
    mensajes = infracciones("import math\nimport os\nimport sys\n")
    assert [m.split(":")[0] for m in mensajes] == ["línea 2", "línea 3"]


def test_comprobar_clase():
    class Propia:
        pass

    Propia.__module__ = "pong.bot"
    assert comprobar_clase(Propia) == []
    assert "pong.bots_ref" in comprobar_clase(Easy)[0]
    assert comprobar_clase(lambda seed: None) == ["Bot no es una clase"]


def test_runner_no_juega_con_un_bot_que_no_cumple(tmp_path, monkeypatch, capsys):
    trampa = tmp_path / "bot.py"
    trampa.write_text("from pong_ref_bots import Hard as Bot\n", encoding="utf-8")
    monkeypatch.setattr(runner, "RUTA_BOT", trampa)
    with pytest.raises(SystemExit):
        runner.cargar_mi_bot()
    assert "línea 1: importa pong_ref_bots" in capsys.readouterr().out


def test_runner_rechaza_una_clase_ajena(monkeypatch):
    import pong.bot

    monkeypatch.setattr(pong.bot, "Bot", Easy)
    with pytest.raises(SystemExit, match="no cumple las normas"):
        runner.cargar_mi_bot()


def test_modulos_permitidos_no_incluyen_el_paquete():
    assert not {"pong", "pong_ref_bots"} & normas.MODULOS_PERMITIDOS
