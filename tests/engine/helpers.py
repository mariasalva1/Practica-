"""Utilidades de los tests del motor: bots triviales y preparación de estados.

No son los bots de referencia de ``pong.bots_ref``.
"""

from __future__ import annotations

import random

from pong import pong_engine as pe


class StayBot:
    """No se mueve nunca."""

    def __init__(self, seed: int = 0) -> None:
        self.seed = seed

    def decide(self, state: dict) -> str:
        return "STAY"


class FollowerBot:
    """Sigue la ordenada de la bola con una zona muerta de 4 px."""

    def __init__(self, seed: int = 0) -> None:
        self.seed = seed

    def decide(self, state: dict) -> str:
        diff = state["ball_y"] - state["my_paddle_y"]
        if diff > 4.0:
            return "DOWN"
        if diff < -4.0:
            return "UP"
        return "STAY"


class NoisyFollowerBot(FollowerBot):
    """Seguidor que, con probabilidad 0.2, devuelve un comando al azar.

    Usa su propia semilla: sirve para comprobar que la partida depende de
    las semillas de los bots (2·seed + 1 y 2·seed + 2).
    """

    def __init__(self, seed: int = 0) -> None:
        super().__init__(seed)
        self.rng = random.Random(seed)

    def decide(self, state: dict) -> str:
        if self.rng.random() < 0.2:
            return self.rng.choice(["UP", "DOWN", "STAY"])
        return super().decide(state)


class ScriptBot:
    """Devuelve siempre el mismo valor, válido o no."""

    def __init__(self, value: object) -> None:
        self.value = value

    def decide(self, state: dict) -> object:
        return self.value


class RaisingBot:
    """Lanza una excepción en cada llamada."""

    def decide(self, state: dict) -> str:
        raise ValueError("fallo del bot")


class MutatingBot(FollowerBot):
    """Modifica el diccionario recibido, incluido field."""

    def decide(self, state: dict) -> str:
        state["ball_x"] = -1.0
        state["field"]["width"] = 0.0
        state.clear()
        return "STAY"


def put_in_play(
    match: pe.Match,
    *,
    x: float,
    y: float,
    vx: float,
    vy: float,
    ay: float = 0.0,
    speed: float | None = None,
    p_left: float | None = None,
    p_right: float | None = None,
) -> pe.Match:
    """Coloca la partida en estado ``playing`` con la bola indicada."""
    match.phase = pe.PLAYING
    match.serve_ticks_left = 0
    match.ball_x, match.ball_y = x, y
    match.vx, match.vy, match.ay = vx, vy, ay
    if speed is not None:
        match.speed = speed
    if p_left is not None:
        match.paddles[pe.LEFT] = p_left
    if p_right is not None:
        match.paddles[pe.RIGHT] = p_right
    return match
