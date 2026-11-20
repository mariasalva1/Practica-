"""Saque, rotación, puntuación, victoria y límites de terminación.

Enunciado de la práctica, apartados 2.7–2.9.
"""

from __future__ import annotations

import random

import pytest
from helpers import put_in_play

from pong import pong_engine as pe


def lose_point(m: pe.Match, loser: int) -> None:
    """Hace que ``loser`` falle la bola en el tick siguiente."""
    if loser == pe.LEFT:
        put_in_play(m, x=50.0, y=300.0, vx=-20.0, vy=0.0, p_left=100.0)
    else:
        put_in_play(m, x=750.0, y=300.0, vx=20.0, vy=0.0, p_right=100.0)
    m.step("STAY", "STAY")


def hit(m: pe.Match, side: int) -> None:
    """Hace que ``side`` devuelva la bola en el tick siguiente."""
    if side == pe.LEFT:
        put_in_play(m, x=50.0, y=300.0, vx=-20.0, vy=0.0, p_left=300.0)
    else:
        put_in_play(m, x=750.0, y=300.0, vx=20.0, vy=0.0, p_right=300.0)
    m.step("STAY", "STAY")


# --- condición de victoria de set --------------------------------------------------


@pytest.mark.parametrize(
    "a, b, won",
    [
        (11, 0, True),
        (11, 9, True),
        (10, 9, False),
        (11, 10, False),
        (10, 10, False),
        (12, 10, True),
        (12, 11, False),
        (13, 11, True),
        (14, 13, False),
        (14, 14, False),
        (15, 14, True),
        (15, 13, True),
    ],
)
def test_set_won(a, b, won):
    assert pe.set_won(a, b) is won


@pytest.mark.parametrize(
    "start, winner_needs",
    [((10, 10), 2), ((14, 14), 1), ((13, 13), 2), ((10, 9), 1), ((9, 10), 3)],
)
def test_set_finishes_through_engine(start, winner_needs):
    m = pe.Match(0)
    m.points = list(start)
    for i in range(winner_needs):
        assert m.sets == [0, 0], f"el set acabó antes de tiempo ({i})"
        lose_point(m, pe.RIGHT)
    assert m.sets == [1, 0] and m.points == [0, 0]


def test_golden_point_ends_set_15_14():
    m = pe.Match(0)
    m.points = [14, 14]
    lose_point(m, pe.LEFT)
    assert m.sets == [0, 1] and m.points == [0, 0]
    assert m.rallies[-1]["winner"] == "right"


def test_match_is_best_of_three():
    m = pe.Match(0)
    m.sets = [1, 1]
    m.points = [10, 5]
    lose_point(m, pe.RIGHT)
    assert m.over and m.result == "left" and m.sets == [2, 1]
    with pytest.raises(RuntimeError):
        m.step("STAY", "STAY")


# --- saque y rotación --------------------------------------------------------------


def test_first_server_and_serve_draw_order():
    for seed in range(50):
        rng = random.Random(seed)
        server = pe.LEFT if rng.random() < 0.5 else pe.RIGHT
        slope = pe.SERVE_M_LO + (1.0 - pe.SERVE_M_LO) * rng.random()
        if not rng.random() < 0.5:
            slope = -slope
        m = pe.Match(seed)
        assert m.server == server
        assert m.vy / abs(m.vx) == pytest.approx(slope)
        assert (m.vx > 0) == (server == pe.LEFT)  # hacia el receptor
        assert m.rng.getstate() == rng.getstate()


def test_serve_slope_range_and_speed():
    for seed in range(300):
        m = pe.Match(seed)
        slope = abs(m.vy / m.vx)
        assert pe.SERVE_M_LO - 1e-12 <= slope <= 1.0
        assert (m.vx * m.vx + m.vy * m.vy) ** 0.5 == pytest.approx(pe.S0)


def test_serving_pause():
    m = pe.Match(4)
    seen = []
    for _ in range(pe.SERVE_PAUSE):
        st = m.state_for(pe.LEFT)
        assert st["state"] == "serving"
        assert (st["ball_x"], st["ball_y"]) == (400.0, 300.0)
        seen.append(st["serve_ticks_left"])
        m.step("UP", "DOWN")  # las raquetas se mueven durante la pausa
    assert seen == list(range(60, 0, -1))
    assert m.phase == pe.PLAYING and m.serve_ticks_left == 0
    assert m.paddles == [40.0, 560.0]
    assert (m.ball_x, m.ball_y) == (400.0, 300.0)
    m.step("STAY", "STAY")
    assert m.ball_x != 400.0  # el primer movimiento es en el tick siguiente


def test_point_resets_serve_but_not_paddles():
    m = pe.Match(0)
    put_in_play(
        m,
        x=50.0,
        y=300.0,
        vx=-20.0,
        vy=0.0,
        ay=0.003,
        speed=50.0,
        p_left=100.0,
        p_right=222.0,
    )
    m.rally_hits = 7
    m.step("STAY", "STAY")
    assert m.phase == pe.SERVING and m.serve_ticks_left == 60
    assert (m.ball_x, m.ball_y, m.speed, m.ay, m.rally_hits) == (
        400.0,
        300.0,
        pe.S0,
        0.0,
        0,
    )
    assert m.paddles == [100.0, 222.0]


@pytest.mark.parametrize("scorer", [pe.LEFT, pe.RIGHT])
def test_scorer_serves_next_toward_loser(scorer):
    m = pe.Match(11)
    lose_point(m, 1 - scorer)
    assert m.server == scorer
    assert (m.vx > 0) == (scorer == pe.LEFT)


def test_rotation_over_several_points():
    m = pe.Match(5)
    for loser in [pe.LEFT, pe.LEFT, pe.RIGHT, pe.LEFT, pe.RIGHT, pe.RIGHT]:
        lose_point(m, loser)
        assert m.server == 1 - loser
        assert m.state_for(1 - loser)["serving"] == "me"
        assert m.state_for(loser)["serving"] == "opp"


@pytest.mark.parametrize("set_winner", [pe.LEFT, pe.RIGHT])
def test_set_loser_serves_first_in_next_set(set_winner):
    m = pe.Match(2)
    m.points[set_winner] = 10
    lose_point(m, 1 - set_winner)
    assert m.sets[set_winner] == 1
    assert m.server == 1 - set_winner
    # La bola va hacia el receptor, que es quien ganó el set.
    assert (m.vx > 0) == (m.server == pe.LEFT)


# --- límites de terminación -------------------------------------------------------


def test_99_hits_is_not_a_let():
    m = pe.Match(0)
    m.rally_hits = 98
    hit(m, pe.LEFT)
    assert m.rally_hits == 99 and m.lets == 0 and m.phase == pe.PLAYING


def test_100th_hit_is_a_let():
    m = pe.Match(0)
    server = m.server
    m.points = [3, 4]
    m.rally_hits = 99
    hit(m, pe.RIGHT)
    assert m.lets == 1 and m.points == [3, 4] and m.sets == [0, 0]
    assert m.phase == pe.SERVING and m.rally_hits == 0 and m.serve_ticks_left == 60
    assert m.server == server  # se repite con el mismo jugador
    assert m.rallies[-1] == {
        "start_tick": 0,
        "end_tick": 0,
        "hits": 100,
        "outcome": "let",
        "winner": None,
    }


def test_let_counter_and_twentieth_let_is_a_draw():
    m = pe.Match(0)
    for i in range(1, 20):
        m.rally_hits = 99
        hit(m, pe.LEFT)
        assert m.lets == i and not m.over
        assert m.state_for(pe.RIGHT)["lets"] == i
    m.rally_hits = 99
    hit(m, pe.LEFT)
    assert m.lets == 20 and m.over and m.result == "draw"
    assert m.state_for(pe.LEFT)["state"] == "match_over"


def test_lets_accumulate_across_sets():
    m = pe.Match(0)
    m.lets = 19
    m.sets = [1, 0]
    m.rally_hits = 99
    hit(m, pe.RIGHT)
    assert m.result == "draw"


def test_full_rally_reaches_let_naturally():
    # 100 golpes reales, alternando lados, sin manipular rally_hits.
    m = pe.Match(0)
    for i in range(100):
        assert m.lets == 0
        hit(m, pe.LEFT if i % 2 == 0 else pe.RIGHT)
    assert m.lets == 1 and m.rallies[-1]["hits"] == 100
