"""Tests de tu bot: punto de partida (1 punto de 10; enunciado, apartado 5).

Amplía este fichero con tests de tu predictor contra el motor: por ejemplo,
que la ordenada de cruce que predices coincide con la del motor en esquinas
y con varios rebotes en un mismo tick.
"""

from pong import pong_engine as pe
from pong.bot import Bot
from pong.bots_ref import Easy

COMANDOS = {"UP", "DOWN", "STAY"}


def test_devuelve_comandos_validos_durante_una_partida():
    match = pe.Match(1)
    mi_bot, rival = Bot(3), Easy(4)
    for _ in range(2000):
        comando = mi_bot.decide(match.state_for(pe.LEFT))
        assert comando in COMANDOS
        match.step(comando, rival.decide(match.state_for(pe.RIGHT)))


def test_funciona_en_el_lado_derecho():
    match = pe.Match(2)
    mi_bot, rival = Bot(5), Easy(6)
    for _ in range(2000):
        comando = mi_bot.decide(match.state_for(pe.RIGHT))
        assert comando in COMANDOS
        match.step(rival.decide(match.state_for(pe.LEFT)), comando)
