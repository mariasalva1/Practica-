"""Cruce del plano, franja de impacto, física del golpe y ausencia de tunnelling."""

from __future__ import annotations

import math
import random

import pytest
from helpers import put_in_play

from pong import pong_engine as pe

NEXT_UP = lambda v: math.nextafter(v, math.inf)  # noqa: E731
NEXT_DOWN = lambda v: math.nextafter(v, -math.inf)  # noqa: E731


def left_shot(y: float, p: float, vy: float = 0.0) -> pe.Match:
    """Bola que cruza el plano izquierdo en τ* = 0.7 con raqueta en p."""
    return put_in_play(pe.Match(7), x=50.0, y=y, vx=-20.0, vy=vy, speed=10.0, p_left=p)


def right_shot(y: float, p: float) -> pe.Match:
    return put_in_play(
        pe.Match(7), x=750.0, y=y, vx=20.0, vy=0.0, speed=10.0, p_right=p
    )


@pytest.mark.parametrize("offset", [pe.HALF_REACH, -pe.HALF_REACH])
def test_band_edge_is_a_hit_left(offset):
    m = left_shot(300.0 + offset, 300.0)
    m.step("STAY", "STAY")
    assert m.rally_hits == 1 and m.phase == pe.PLAYING
    assert m.ball_x == pe.X_L + pe.R
    assert m.ball_y == 300.0 + offset
    sign = 1.0 if offset > 0 else -1.0
    root = math.sqrt(1.0 + pe.M_MAX * pe.M_MAX)
    speed = pe.SPEEDUP * (1.0 + pe.EDGE_SPEEDUP * 1.0) * 10.0
    assert m.speed == speed
    assert m.vx == speed / root
    assert m.vy == speed * (sign * pe.M_MAX) / root


@pytest.mark.parametrize("y", [NEXT_UP(346.0), NEXT_DOWN(254.0)])
def test_just_outside_band_is_a_point_left(y):
    m = left_shot(y, 300.0)
    m.step("STAY", "STAY")
    assert m.points == [0, 1]
    assert m.phase == pe.SERVING
    assert m.rallies[-1]["outcome"] == "point" and m.rallies[-1]["winner"] == "right"


@pytest.mark.parametrize(
    "y, hit",
    [(346.0, True), (254.0, True), (NEXT_UP(346.0), False), (NEXT_DOWN(254.0), False)],
)
def test_band_edges_right(y, hit):
    m = right_shot(y, 300.0)
    m.step("STAY", "STAY")
    if hit:
        assert m.rally_hits == 1 and m.ball_x == pe.X_R - pe.R and m.vx < 0
    else:
        assert m.points == [1, 0]


def test_band_uses_paddle_after_moving():
    # La raqueta se mueve antes que la bola (paso 2): 300 → 308.
    m = left_shot(354.0, 300.0)
    m.step("DOWN", "STAY")
    assert m.paddles[pe.LEFT] == 308.0 and m.rally_hits == 1


def test_band_uses_interpolated_folded_y():
    # y* = F(Y(τ*)) con τ* = 0.7: 590 + 0.7·10 = 597 → plegado 591.
    m = left_shot(590.0, 560.0, vy=10.0)
    m.step("STAY", "STAY")
    assert m.ball_y == pytest.approx(591.0)
    assert m.rally_hits == 1


def test_no_collision_with_paddle_ends():
    # Cruzar el plano fuera de la franja es punto aunque la bola "roce" el canto.
    m = left_shot(300.0 + pe.HALF_REACH + 0.5, 300.0)
    m.step("STAY", "STAY")
    assert m.points == [0, 1]


def test_center_hit_sign_comes_from_engine_rng():
    m = left_shot(300.0, 300.0)
    expected_rng = random.Random()
    expected_rng.setstate(m.rng.getstate())
    expected_sign = 1.0 if expected_rng.random() < 0.5 else -1.0
    m.step("STAY", "STAY")
    root = math.sqrt(1.0 + pe.M_MIN * pe.M_MIN)
    assert m.vy == m.speed * (expected_sign * pe.M_MIN) / root
    assert m.speed == pe.SPEEDUP * 1.0 * 10.0


def test_min_slope_near_center():
    m = left_shot(301.0, 300.0)  # |u| = 1/46: m_max·|u| < m_min
    m.step("STAY", "STAY")
    assert m.vy / m.vx == pytest.approx(pe.M_MIN)


def test_outgoing_vx_at_least_half_speed():
    for off in [i * 0.5 for i in range(-92, 93)]:
        m = left_shot(300.0 + off, 300.0)
        m.step("STAY", "STAY")
        assert m.vx >= m.speed / 2.0 - 1e-12
        assert math.hypot(m.vx, m.vy) == pytest.approx(m.speed)


@pytest.mark.parametrize(
    "cmd, ay", [("UP", -pe.KAPPA), ("STAY", 0.0), ("DOWN", pe.KAPPA)]
)
def test_spin_from_hitting_command(cmd, ay):
    m = left_shot(300.0, 300.0)
    m.step(cmd, "STAY")
    assert m.ay == ay


def test_spin_uses_command_even_at_paddle_limit():
    # Por diseño: la raqueta en el tope no se mueve, pero DOWN da ay = +κ.
    m = left_shot(560.0, 560.0)
    m.step("DOWN", "STAY")
    assert m.paddles[pe.LEFT] == 560.0 and m.ay == pe.KAPPA


def test_spin_applies_from_next_tick():
    m = left_shot(300.0, 300.0)
    m.step("DOWN", "STAY")
    vy_after_hit = m.vy
    y_after_hit = m.ball_y
    m.step("STAY", "STAY")
    assert m.vy == vy_after_hit + pe.KAPPA
    assert m.ball_y == y_after_hit + (vy_after_hit + pe.KAPPA)


def test_crossing_exactly_at_tick_end_is_resolved_next_tick():
    # Por diseño: X(1) − r = X_L no es cruce; se resuelve con τ* = 0.
    m = put_in_play(
        pe.Match(1), x=56.0, y=300.0, vx=-20.0, vy=0.0, speed=10.0, p_left=300.0
    )
    m.step("STAY", "STAY")
    assert m.ball_x == 36.0 and m.rally_hits == 0 and m.phase == pe.PLAYING
    m.step("STAY", "STAY")
    assert m.rally_hits == 1 and m.ball_x == 36.0


@pytest.mark.parametrize("speed", [1e3, 1e6, 1e12])
@pytest.mark.parametrize("aligned", [True, False])
def test_no_tunnelling_left(speed, aligned):
    p = 300.0 if aligned else 100.0
    m = put_in_play(
        pe.Match(3), x=400.0, y=300.0, vx=-speed, vy=0.0, speed=speed, p_left=p
    )
    m.step("STAY", "STAY")
    if aligned:
        assert m.rally_hits == 1 and m.ball_x == pe.X_L + pe.R and m.vx > 0
    else:
        assert m.points == [0, 1]


@pytest.mark.parametrize("speed", [1e3, 1e6, 1e12])
def test_no_tunnelling_right_with_wall_bounces(speed):
    # vx y vy enormes: muchos rebotes y cruce del plano en el mismo tick.
    vx = speed
    vy = speed * 0.9
    tau = (pe.X_R - 400.0 - pe.R) / vx
    y_star = pe.fold(300.0 + tau * vy)[0]
    m = put_in_play(
        pe.Match(3),
        x=400.0,
        y=300.0,
        vx=vx,
        vy=vy,
        speed=speed,
        p_right=min(max(y_star, 40.0), 560.0),
    )
    m.step("STAY", "STAY")
    # p = y* recortado a [40, 560] queda siempre a ≤ 34 px de y*: hay impacto.
    assert m.rally_hits == 1
    assert m.ball_x == pe.X_R - pe.R and m.ball_y == y_star and m.vx < 0


def test_no_tunnelling_property():
    # En miles de vuelos a gran velocidad la bola nunca queda tras una cara.
    rng = random.Random(99)
    for _ in range(2000):
        speed = 10 ** rng.uniform(3, 8)  # |vx| > 728: cruza en un tick
        m = put_in_play(
            pe.Match(5),
            x=rng.uniform(40.0, 760.0),
            y=rng.uniform(6.0, 594.0),
            vx=rng.choice([-1, 1]) * speed,
            vy=rng.uniform(-3, 3) * speed,
            speed=speed,
            p_left=rng.uniform(40, 560),
            p_right=rng.uniform(40, 560),
        )
        hits_before, points_before = m.rally_hits, sum(m.points)
        m.step("STAY", "STAY")
        crossed = m.rally_hits > hits_before or sum(m.points) > points_before
        assert crossed, "a esa velocidad la bola debe llegar a una cara en un tick"
        assert pe.X_L + pe.R <= m.ball_x <= pe.X_R - pe.R
