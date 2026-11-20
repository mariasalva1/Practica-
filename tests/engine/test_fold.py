"""F: rango, periodicidad, paridad y varios rebotes en un mismo tick.

Enunciado de la práctica, apartado 2.4.
"""

from __future__ import annotations

import math
import random

import pytest
from helpers import put_in_play

from pong import pong_engine as pe

R, L, TWO_L = pe.R, pe.L, pe.TWO_L


def sample_values(n: int = 20000) -> list[float]:
    rng = random.Random(1234)
    values = [rng.uniform(-1e5, 1e5) for _ in range(n)]
    values += [rng.uniform(-3000.0, 3000.0) for _ in range(n)]
    values += [R + j * L + e for j in range(-6, 7) for e in (-1e-9, 0.0, 1e-9)]
    return values


def test_range():
    for v in sample_values():
        y, k = pe.fold(v)
        assert R <= y <= pe.H - R
        assert k in (0, 1)


def test_identity_inside_field():
    for v in [R, 100.0, 300.0, 593.999, 123.456]:
        assert pe.fold(v) == (v, 0)


def test_wall_contact_convention():
    # z = L exactamente: la fórmula da k = 1 (la bola que llega bajando a la
    # pared inferior ya cuenta como reflejada). Es coherente: en el tick
    # siguiente la bola se aleja de la pared con cualquiera de los dos signos.
    assert pe.fold(pe.H - R) == (pe.H - R, 1)
    assert pe.fold(R) == (R, 0)


def test_periodicity_exact_on_integers():
    # Con enteros, Y + 2L·j es exacto y F debe coincidir bit a bit.
    for v in range(-3000, 3001, 7):
        for j in (-3, -1, 1, 4):
            assert pe.fold(float(v)) == pe.fold(float(v) + j * TWO_L)


def test_periodicity_floats():
    for v in sample_values(5000):
        a, ka = pe.fold(v)
        b, kb = pe.fold(v + TWO_L)
        assert math.isclose(a, b, abs_tol=1e-9)
        # La paridad solo puede discrepar por redondeo justo en la pared.
        assert ka == kb or min(a - R, pe.H - R - a) < 1e-6


def test_symmetry_about_wall():
    # Reflejar respecto a la pared inferior (Y = H − r) no cambia F.
    for d in [0.5, 10.0, 200.0, 587.0]:
        assert pe.fold(pe.H - R + d)[0] == pytest.approx(pe.fold(pe.H - R - d)[0])


@pytest.mark.parametrize(
    "y_unfolded, parity",
    [
        (R, 0),
        (R + L - 1e-6, 0),  # z ∈ [0, L): sin reflexión
        (R + L, 1),
        (R + 2 * L - 1e-6, 1),  # z ∈ [L, 2L): una
        (R + 2 * L, 0),
        (R + 3 * L, 1),  # dos, tres
        (R - 1e-6, 1),
        (R - L, 1),  # z ∈ [−L, 0): una (pared superior)
        (R - L - 1e-6, 0),
        (R - 2 * L, 0),  # z ∈ [−2L, −L): dos
        (R - 2 * L - 1e-6, 1),  # tres
    ],
)
def test_parity(y_unfolded, parity):
    assert pe.fold(y_unfolded)[1] == parity


def test_parity_matches_formula():
    for v in sample_values(5000):
        z = v - R
        assert pe.fold(v)[1] == math.floor(z / L) % 2


def test_three_wall_bounces_in_one_tick():
    # 300 → 594 (1) → 6 (2) → 594 (3) → sube 30 → 564; vy queda negativa.
    m = put_in_play(pe.Match(0), x=400.0, y=300.0, vx=1.0, vy=1499.5, ay=0.5)
    m.step("STAY", "STAY")  # vy ← 1499.5 + 0.5 = 1500 antes de mover
    assert m.ball_y == 564.0
    assert m.ball_x == 401.0
    assert m.vy == -1500.0
    assert m.ay == -0.5


def test_two_wall_bounces_in_one_tick():
    # 300 → 594 (1) → 6 (2) → baja 318 → 324; vy conserva el signo.
    m = put_in_play(pe.Match(0), x=400.0, y=300.0, vx=1.0, vy=1199.5, ay=0.5)
    m.step("STAY", "STAY")
    assert m.ball_y == 324.0
    assert m.vy == 1200.0
    assert m.ay == 0.5


def test_many_bounces_upwards():
    # 101 reflexiones (impar) hacia arriba.
    vy = -(294.0 + 100 * L + 10.0)
    m = put_in_play(pe.Match(0), x=400.0, y=300.0, vx=1.0, vy=vy)
    m.step("STAY", "STAY")
    assert m.ball_y == pytest.approx(R + 10.0)
    assert m.vy > 0


def test_closed_form_matches_simulation_without_walls():
    # Enunciado, apartado 2.6: y_n = y_0 + n·vy_0 + ay·n(n+1)/2 (sin rebotes ni golpes).
    m = put_in_play(pe.Match(0), x=100.0, y=300.0, vx=3.0, vy=0.5, ay=0.005)
    for n in range(1, 101):
        m.step("STAY", "STAY")
        assert m.ball_y == pytest.approx(
            300.0 + n * 0.5 + 0.005 * n * (n + 1) / 2, abs=1e-9
        )
        assert m.ball_x == pytest.approx(100.0 + 3.0 * n)
