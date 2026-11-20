"""Motor de reglas de la práctica Pong (especificación técnica v1.0).

Módulo en Python puro, sin entrada/salida: no lee ni escribe ficheros, no
imprime y no mide tiempos. Lo importan sin modificarlo ``runner.py``,
``pong.html`` (vía Pyodide) y ``tournament.py``.

Determinismo
------------
Toda la aritmética en coma flotante usa solo ``+``, ``-``, ``*``, ``/``,
``math.sqrt``, ``math.floor`` y ``%``, que IEEE 754 exige correctamente
redondeadas, más operaciones exactas que no redondean (comparaciones,
``abs``, ``min``, ``max`` y el cambio de signo). Todo el azar sale de un único
``random.Random(seed)`` consumido en un orden fijo. Por tanto, misma
versión, misma semilla y misma lista de comandos producen la misma partida,
bit a bit, en CPython y en Pyodide.

El orden de evaluación de cada expresión forma parte de la especificación:
``1.05 * (1.0 + 0.05 * abs(u)) * s`` no es bit a bit igual que
``1.05 * s * (1.0 + 0.05 * abs(u))``. Las expresiones de este módulo son la
referencia.

Uso típico
----------
>>> match, commands = play_match(42, MiBot, OtroBot)   # doctest: +SKIP
>>> replay(42, commands).snapshot() == match.snapshot() # doctest: +SKIP
True
"""

from __future__ import annotations

import math
import random
from typing import Callable, Protocol

ENGINE_VERSION = "1.0"
PROTOCOL_VERSION = "1.0"

# --- §2 Geometría y unidades ------------------------------------------------
W = 800.0  # ancho del campo (px)
H = 600.0  # alto del campo (px)
R = 6.0  # radio de la bola, r (px)
PADDLE_H = 80.0  # alto de la raqueta, h (px)
PADDLE_THICKNESS = 10.0  # grosor de la raqueta (px)
X_L = 30.0  # cara de la raqueta izquierda (px)
X_R = 770.0  # cara de la raqueta derecha (px)
PADDLE_SPEED = 8.0  # v_p (px/tick)
S0 = 6.0  # velocidad inicial de la bola, s_0 (px/tick)

P_MIN = PADDLE_H / 2.0  # 40.0
P_MAX = H - PADDLE_H / 2.0  # 560.0
L = H - 2.0 * R  # 588.0, recorrido vertical del centro
TWO_L = 2.0 * L  # 1176.0, periodo de F
HALF_REACH = PADDLE_H / 2.0 + R  # 46.0, semiancho de la franja de impacto

# --- §4 Físicas de impacto ----------------------------------------------------
M_MAX = 1.7320508075688772  # literal de tan 60°
M_MIN = 0.0874886635259240  # literal de tan 5°
SPEEDUP = 1.05  # aceleración por golpe
EDGE_SPEEDUP = 0.05  # velocidad extra en los extremos
KAPPA = 0.005  # efecto, px/tick²

# --- §5 Saque -----------------------------------------------------------------
SERVE_PAUSE = 60
SERVE_M_LO = 0.3639702342662024  # literal de tan 20°
SERVE_M_HI = 1.0  # tan 45°
CENTER_X = 400.0
CENTER_Y = 300.0
PADDLE_START = 300.0  # decisión D1: no fijado en la especificación

# --- §6 y §7 Puntuación y terminación ----------------------------------------------
SETS_TO_WIN = 2
R_MAX = 100
MAX_LETS = 20
MAX_MATCH_TICKS = 2_606_520  # cota demostrada en §7 (D9)

LEFT = 0
RIGHT = 1

SERVING = "serving"
PLAYING = "playing"
MATCH_OVER = "match_over"

COMMAND_VALUES: dict[str, int] = {"UP": -1, "STAY": 0, "DOWN": 1}

STATE_KEYS: tuple[str, ...] = (
    "protocol_version",
    "tick",
    "state",
    "ball_x",
    "ball_y",
    "my_paddle_y",
    "opp_paddle_y",
    "my_points",
    "opp_points",
    "my_sets",
    "opp_sets",
    "serving",
    "serve_ticks_left",
    "rally_hits",
    "lets",
    "field",
)

FIELD: dict[str, float | int] = {
    # §2 (normalizado: la cara propia siempre está en x = 30)
    "width": W,
    "height": H,
    "ball_radius": R,
    "paddle_height": PADDLE_H,
    "paddle_thickness": PADDLE_THICKNESS,
    "my_face_x": X_L,
    "opp_face_x": X_R,
    "paddle_speed": PADDLE_SPEED,
    "initial_speed": S0,
    # §4
    "slope_max": M_MAX,
    "slope_min": M_MIN,
    "speedup": SPEEDUP,
    "edge_speedup": EDGE_SPEEDUP,
    "spin_kappa": KAPPA,
    # §5 y §7 (int): duración de la pausa del saque y límites de terminación
    "serve_pause": SERVE_PAUSE,
    "max_rally_hits": R_MAX,
    "max_lets": MAX_LETS,
}


class BotLike(Protocol):
    """Interfaz del bot de los alumnos (§8)."""

    def decide(self, state: dict) -> str:
        """Devuelve ``"UP"``, ``"DOWN"`` o ``"STAY"``."""
        ...


# ---------------------------------------------------------------------------
# Funciones puras
# ---------------------------------------------------------------------------


def fold(y_unfolded: float) -> tuple[float, int]:
    """Pliega una ordenada desplegada sobre el campo (§3).

    Con z = Y − r: m = z mod 2L; F(Y) = r + m si m ≤ L y r + 2L − m si
    m > L; k = ⌊z / L⌋ mod 2.

    Postcondiciones: R ≤ F(Y) ≤ H − R; F tiene periodo 2L; k ∈ {0, 1} es la
    paridad del número de reflexiones en las paredes.
    """
    z = y_unfolded - R
    m = z % TWO_L
    if m <= L:
        y = R + m
    else:
        y = R + TWO_L - m
    k = math.floor(z / L) % 2
    return y, k


def set_won(a: int, b: int) -> bool:
    """Indica si quien tiene ``a`` puntos frente a ``b`` ha ganado el set (§6).

    (a ≥ 11 ∧ a − b ≥ 2) ∨ a = 15.
    """
    return (a >= 11 and a - b >= 2) or a == 15


def sanitize_command(value: object) -> str:
    """Devuelve ``value`` si es un comando válido y ``"STAY"`` en otro caso.

    Solo valen las cadenas exactas ``"UP"``, ``"DOWN"`` y ``"STAY"``
    (decisión D18: sin normalizar mayúsculas ni espacios).
    """
    try:
        if isinstance(value, str) and value in COMMAND_VALUES:
            return str(value)
    except Exception:
        pass
    return "STAY"


def ask_bot(bot: BotLike, state: dict) -> str:
    """Llama a ``bot.decide(state)``; una excepción o un valor no válido
    cuentan como ``"STAY"`` (§8).

    Solo se capturan subclases de ``Exception``: ``SystemExit`` y
    ``KeyboardInterrupt`` se propagan (decisión D18). El límite de tiempo
    no se aplica aquí, porque medir tiempos rompería el determinismo: es
    responsabilidad de ``tournament.py`` (decisión D15).
    """
    try:
        value = bot.decide(state)
    except Exception:
        return "STAY"
    return sanitize_command(value)


# ---------------------------------------------------------------------------
# Partida
# ---------------------------------------------------------------------------


class Match:
    """Estado completo de una partida y su evolución tick a tick.

    Los atributos son públicos para que los adaptadores (registro CSV,
    visualización) y los tests puedan leerlos; solo ``step`` debe
    modificarlos durante una partida real.

    Atributos en coordenadas globales: ``ball_x``, ``ball_y``, ``vx``,
    ``vy``, ``ay``, ``speed`` (velocidad de intercambio s), ``paddles``
    ([p_L, p_R]), ``points``, ``sets``, ``server`` (LEFT o RIGHT),
    ``phase`` (``"serving"``, ``"playing"`` o ``"match_over"``),
    ``serve_ticks_left``, ``rally_hits``, ``lets``, ``tick`` (índice del
    próximo tick que se va a ejecutar), ``result`` (``None``, ``"left"``,
    ``"right"`` o ``"draw"``) y ``rallies`` (lista de intercambios
    terminados, §10).
    """

    def __init__(self, seed: int) -> None:
        self.seed = seed
        self.rng = random.Random(seed)
        self.tick = 0
        self.phase = SERVING
        self.ball_x = CENTER_X
        self.ball_y = CENTER_Y
        self.vx = 0.0
        self.vy = 0.0
        self.ay = 0.0
        self.speed = S0
        self.paddles = [PADDLE_START, PADDLE_START]
        self.points = [0, 0]
        self.sets = [0, 0]
        self.serve_ticks_left = 0
        self.rally_hits = 0
        self.lets = 0
        self.result: str | None = None
        self.rallies: list[dict] = []
        self.rally_start_tick = 0
        # Primer sorteo: quién saca el primer punto del set 1 (D2, D7).
        self.server = LEFT if self.rng.random() < 0.5 else RIGHT
        self._start_serve()

    # -- consulta --------------------------------------------------------

    @property
    def over(self) -> bool:
        """``True`` cuando la partida ha terminado."""
        return self.phase == MATCH_OVER

    def state_for(self, side: int) -> dict:
        """Estado normalizado que recibe el bot de ``side`` (§8).

        Para el jugador derecho, x → W − x; y no cambia. Devuelve un
        diccionario nuevo en cada llamada (incluido ``field``), de modo que
        modificarlo no afecta al motor.
        """
        other = 1 - side
        ball_x = self.ball_x if side == LEFT else W - self.ball_x
        return {
            "protocol_version": PROTOCOL_VERSION,
            "tick": self.tick,
            "state": self.phase,
            "ball_x": ball_x,
            "ball_y": self.ball_y,
            "my_paddle_y": self.paddles[side],
            "opp_paddle_y": self.paddles[other],
            "my_points": self.points[side],
            "opp_points": self.points[other],
            "my_sets": self.sets[side],
            "opp_sets": self.sets[other],
            "serving": "me" if self.server == side else "opp",
            "serve_ticks_left": self.serve_ticks_left,
            "rally_hits": self.rally_hits,
            "lets": self.lets,
            "field": dict(FIELD),
        }

    def snapshot(self) -> dict:
        """Estado global completo, en coordenadas sin normalizar.

        Sirve para los registros de §10 y para comparar partidas con
        ``repr`` de cada ``float`` (§9).
        """
        return {
            "engine_version": ENGINE_VERSION,
            "seed": self.seed,
            "tick": self.tick,
            "state": self.phase,
            "ball_x": self.ball_x,
            "ball_y": self.ball_y,
            "ball_vx": self.vx,
            "ball_vy": self.vy,
            "ball_ay": self.ay,
            "ball_speed": self.speed,
            "p_left": self.paddles[LEFT],
            "p_right": self.paddles[RIGHT],
            "points": list(self.points),
            "sets": list(self.sets),
            "server": "left" if self.server == LEFT else "right",
            "serve_ticks_left": self.serve_ticks_left,
            "rally_hits": self.rally_hits,
            "lets": self.lets,
            "result": self.result,
        }

    # -- evolución -------------------------------------------------------------

    def step(self, cmd_left: object, cmd_right: object) -> None:
        """Ejecuta un tick con los comandos de ambos jugadores.

        Los comandos no válidos cuentan como ``"STAY"``.

        Precondición: la partida no ha terminado.
        """
        if self.phase == MATCH_OVER:
            raise RuntimeError("la partida ya ha terminado")
        if self.tick >= MAX_MATCH_TICKS:
            raise RuntimeError("se ha superado la cota de §7: error del motor")
        c_left = COMMAND_VALUES[sanitize_command(cmd_left)]
        c_right = COMMAND_VALUES[sanitize_command(cmd_right)]
        self.tick += 1

        # Paso 2 (§3): raquetas. También durante el saque (§5).
        self.paddles[LEFT] = min(
            max(self.paddles[LEFT] + PADDLE_SPEED * c_left, P_MIN), P_MAX
        )
        self.paddles[RIGHT] = min(
            max(self.paddles[RIGHT] + PADDLE_SPEED * c_right, P_MIN), P_MAX
        )

        if self.phase == SERVING:
            # Decisión D5: la bola no se mueve durante la pausa.
            self.serve_ticks_left -= 1
            if self.serve_ticks_left == 0:
                self.phase = PLAYING
            return

        # Paso 3: efecto.
        self.vy = self.vy + self.ay
        x, y, vx, vy = self.ball_x, self.ball_y, self.vx, self.vy
        x1 = x + vx
        y1 = y + vy

        # Paso 5: cruce del plano de la raqueta que recibe.
        if vx < 0.0 and x1 - R < X_L <= x - R:
            tau = (x - R - X_L) / (-vx)
            y_star, _ = fold(y + tau * vy)
            self._resolve_crossing(LEFT, y_star, c_left)
            return
        if vx > 0.0 and x1 + R > X_R >= x + R:
            tau = (X_R - x - R) / vx
            y_star, _ = fold(y + tau * vy)
            self._resolve_crossing(RIGHT, y_star, c_right)
            return

        # Paso 6: sin cruce.
        self.ball_x = x1
        self.ball_y, k = fold(y1)
        if k == 1:
            self.vy = -self.vy
            self.ay = -self.ay

    # -- auxiliares internos ---------------------------------------------------

    def _resolve_crossing(self, side: int, y_star: float, command: int) -> None:
        """Impacto o punto perdido al cruzar el plano de ``side`` (§3.5, §4)."""
        p = self.paddles[side]
        if not abs(y_star - p) <= HALF_REACH:
            self._end_point(winner=1 - side)
            return

        self.ball_x = X_L + R if side == LEFT else X_R - R
        self.ball_y = y_star
        u = (y_star - p) / HALF_REACH
        if u == 0.0:
            sign = 1.0 if self.rng.random() < 0.5 else -1.0
        else:
            sign = 1.0 if u > 0.0 else -1.0
        abs_u = abs(u)
        m = sign * max(M_MIN, M_MAX * abs_u)
        self.speed = SPEEDUP * (1.0 + EDGE_SPEEDUP * abs_u) * self.speed
        sigma = 1.0 if side == LEFT else -1.0
        root = math.sqrt(1.0 + m * m)
        self.vx = sigma * self.speed / root
        self.vy = self.speed * m / root
        # Decisión D8: c es el comando, aunque la raqueta esté en el tope.
        self.ay = KAPPA * command
        self.rally_hits += 1
        if self.rally_hits >= R_MAX:  # decisión D9
            self._end_let()

    def _record_rally(self, outcome: str, winner: int | None) -> None:
        self.rallies.append(
            {
                "start_tick": self.rally_start_tick,
                "end_tick": self.tick - 1,
                "hits": self.rally_hits,
                "outcome": outcome,
                "winner": None
                if winner is None
                else ("left" if winner == LEFT else "right"),
            }
        )

    def _end_point(self, winner: int) -> None:
        """Anota el punto, cierra set o partida y prepara el saque (§5, §6)."""
        self._record_rally("point", winner)
        self.points[winner] += 1
        loser = 1 - winner
        if set_won(self.points[winner], self.points[loser]):
            self.sets[winner] += 1
            self.points = [0, 0]
            if self.sets[winner] == SETS_TO_WIN:
                self._finish("left" if winner == LEFT else "right")
                return
            self.server = loser  # primer saque del set siguiente
        else:
            self.server = winner  # saca quien anota
        self._start_serve()

    def _end_let(self) -> None:
        """Intercambio nulo: se repite el saque con el mismo jugador (§5, §7)."""
        self._record_rally("let", None)
        self.lets += 1
        if self.lets >= MAX_LETS:
            self._finish("draw")
            return
        self._start_serve()

    def _finish(self, result: str) -> None:
        self.phase = MATCH_OVER
        self.result = result
        self.serve_ticks_left = 0
        self.rally_hits = 0

    def _start_serve(self) -> None:
        """Reinicio y sorteo del saque (§5): primero la pendiente, después el signo."""
        self.phase = SERVING
        self.serve_ticks_left = SERVE_PAUSE
        self.ball_x = CENTER_X
        self.ball_y = CENTER_Y
        self.speed = S0
        self.ay = 0.0
        self.rally_hits = 0
        self.rally_start_tick = self.tick
        m = SERVE_M_LO + (SERVE_M_HI - SERVE_M_LO) * self.rng.random()
        if not self.rng.random() < 0.5:
            m = -m
        # Decisión D3: hacia el receptor, el rival de quien saca.
        sigma = 1.0 if self.server == LEFT else -1.0
        root = math.sqrt(1.0 + m * m)
        self.vx = sigma * S0 / root
        self.vy = S0 * m / root


# ---------------------------------------------------------------------------
# Ejecución de partidas
# ---------------------------------------------------------------------------

Command = tuple[str, str]


def run_match(match: Match, bot_left: BotLike, bot_right: BotLike) -> list[Command]:
    """Juega ``match`` hasta el final y devuelve la lista de comandos aplicados."""
    commands: list[Command] = []
    while not match.over:
        c_left = ask_bot(bot_left, match.state_for(LEFT))
        c_right = ask_bot(bot_right, match.state_for(RIGHT))
        commands.append((c_left, c_right))
        match.step(c_left, c_right)
    return commands


def play_match(
    seed: int,
    left_factory: Callable[[int], BotLike],
    right_factory: Callable[[int], BotLike],
) -> tuple[Match, list[Command]]:
    """Crea los bots con sus semillas (§9: 2·seed + 1 y 2·seed + 2) y juega."""
    bot_left = left_factory(2 * seed + 1)
    bot_right = right_factory(2 * seed + 2)
    match = Match(seed)
    commands = run_match(match, bot_left, bot_right)
    return match, commands


def replay(seed: int, commands: list[Command]) -> Match:
    """Reproduce una partida a partir de su semilla y su lista de comandos."""
    match = Match(seed)
    for c_left, c_right in commands:
        match.step(c_left, c_right)
    return match
