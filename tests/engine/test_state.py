"""Diccionario de estado, normalización e interfaz con el bot.

Enunciado de la práctica, apartado 3.2.
"""

from __future__ import annotations

from helpers import (
    FollowerBot,
    MutatingBot,
    RaisingBot,
    ScriptBot,
    StayBot,
    put_in_play,
)

from pong import pong_engine as pe

EXPECTED_KEYS = {
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
}
EXPECTED_FIELD_KEYS = {
    "width",
    "height",
    "ball_radius",
    "paddle_height",
    "paddle_thickness",
    "my_face_x",
    "opp_face_x",
    "paddle_speed",
    "initial_speed",
    "slope_max",
    "slope_min",
    "speedup",
    "edge_speedup",
    "spin_kappa",
    "serve_pause",
    "max_rally_hits",
    "max_lets",
}
INT_FIELD_KEYS = {"serve_pause", "max_rally_hits", "max_lets"}
TYPES = {
    "protocol_version": str,
    "tick": int,
    "state": str,
    "ball_x": float,
    "ball_y": float,
    "my_paddle_y": float,
    "opp_paddle_y": float,
    "my_points": int,
    "opp_points": int,
    "my_sets": int,
    "opp_sets": int,
    "serving": str,
    "serve_ticks_left": int,
    "rally_hits": int,
    "lets": int,
    "field": dict,
}


def test_exact_keys_and_types():
    m = pe.Match(0)
    for _ in range(200):
        for side in (pe.LEFT, pe.RIGHT):
            st = m.state_for(side)
            assert set(st) == EXPECTED_KEYS
            assert tuple(st) == pe.STATE_KEYS
            for key, typ in TYPES.items():
                assert type(st[key]) is typ, key
            assert set(st["field"]) == EXPECTED_FIELD_KEYS
            for key, value in st["field"].items():
                assert type(value) is (int if key in INT_FIELD_KEYS else float), key
            assert (
                st["field"]["serve_pause"],
                st["field"]["max_rally_hits"],
                st["field"]["max_lets"],
            ) == (60, 100, 20)
            assert st["protocol_version"] == "1.0"
            assert st["state"] in ("serving", "playing", "match_over")
        m.step("STAY", "STAY")


def test_no_velocities_in_state():
    st = pe.Match(0).state_for(pe.LEFT)
    assert not {"ball_vx", "ball_vy", "ball_ay", "ball_speed"} & set(st)


def test_normalization_right_player():
    m = pe.Match(0)
    put_in_play(m, x=123.25, y=456.5, vx=5.0, vy=1.0, p_left=100.0, p_right=500.0)
    m.points, m.sets, m.server = [3, 7], [1, 0], pe.RIGHT
    left, right = m.state_for(pe.LEFT), m.state_for(pe.RIGHT)
    assert left["ball_x"] == 123.25 and right["ball_x"] == 800.0 - 123.25
    assert left["ball_y"] == right["ball_y"] == 456.5
    assert (right["my_paddle_y"], right["opp_paddle_y"]) == (500.0, 100.0)
    assert (left["my_paddle_y"], left["opp_paddle_y"]) == (100.0, 500.0)
    assert (right["my_points"], right["opp_points"]) == (7, 3)
    assert (right["my_sets"], right["opp_sets"]) == (0, 1)
    assert (right["serving"], left["serving"]) == ("me", "opp")
    assert right["field"] == left["field"]
    assert right["field"]["my_face_x"] == 30.0


def test_right_player_sees_own_face_at_30_and_approaching_ball_decreasing():
    m = pe.Match(0)
    put_in_play(m, x=700.0, y=300.0, vx=20.0, vy=0.0, p_right=300.0)
    xs = []
    for _ in range(4):
        xs.append(m.state_for(pe.RIGHT)["ball_x"])
        m.step("STAY", "STAY")
    assert xs == sorted(xs, reverse=True)
    assert m.rally_hits == 1
    assert m.state_for(pe.RIGHT)["ball_x"] == 30.0 + pe.R


def test_state_is_a_copy():
    m = pe.Match(0)
    before = m.snapshot()
    st = m.state_for(pe.LEFT)
    MutatingBot().decide(st)
    assert m.snapshot() == before
    assert m.state_for(pe.LEFT)["field"]["width"] == 800.0
    pe.run_match(m, MutatingBot(), StayBot())  # no rompe la partida


def test_invalid_values_count_as_stay():
    for bad in [
        None,
        "up",
        " UP",
        "UP\n",
        "LEFT",
        1,
        -1,
        0,
        b"UP",
        ["UP"],
        3.0,
        {"UP": 1},
    ]:
        assert pe.ask_bot(ScriptBot(bad), {}) == "STAY"
        assert pe.sanitize_command(bad) == "STAY"
    for good in ["UP", "DOWN", "STAY"]:
        assert pe.ask_bot(ScriptBot(good), {}) == good


def test_exception_counts_as_stay():
    assert pe.ask_bot(RaisingBot(), {}) == "STAY"


def test_invalid_or_raising_bot_does_not_move_in_match():
    for bad_bot in [RaisingBot(), ScriptBot("up"), ScriptBot(None), ScriptBot(42)]:
        m = pe.Match(3)
        commands = []
        for _ in range(100):
            c_l = pe.ask_bot(bad_bot, m.state_for(pe.LEFT))
            c_r = pe.ask_bot(FollowerBot(), m.state_for(pe.RIGHT))
            commands.append((c_l, c_r))
            m.step(c_l, c_r)
        assert m.paddles[pe.LEFT] == 300.0
        assert all(c == "STAY" for c, _ in commands)


def test_step_sanitizes_raw_commands():
    a, b = pe.Match(8), pe.Match(8)
    for _ in range(80):
        a.step("garbage", None)
        b.step("STAY", "STAY")
    assert a.snapshot() == b.snapshot()


def test_raising_bot_loses_full_match_but_match_ends():
    m, commands = pe.play_match(5, lambda s: RaisingBot(), FollowerBot)
    assert m.over and m.result == "right"
    assert {c for c, _ in commands} == {"STAY"}
