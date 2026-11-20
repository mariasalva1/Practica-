"""Determinismo y reproducción de partidas (enunciado, apartado 2.10)."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from golden import (
    GOLDEN_PATH,
    decode_commands,
    record_golden,
    repr_floats,
    trace_digest,
)
from helpers import FollowerBot, NoisyFollowerBot, StayBot

from pong import pong_engine as pe


@pytest.mark.parametrize("seed", [0, 1, 17, 2026])
def test_same_seed_same_match(seed):
    m1, c1 = pe.play_match(seed, FollowerBot, NoisyFollowerBot)
    m2, c2 = pe.play_match(seed, FollowerBot, NoisyFollowerBot)
    assert c1 == c2
    assert repr_floats(m1.snapshot()) == repr_floats(m2.snapshot())
    assert m1.rallies == m2.rallies
    assert m1.over and m1.result in ("left", "right", "draw")


def test_different_seeds_differ():
    a = pe.play_match(1, FollowerBot, NoisyFollowerBot)[1]
    b = pe.play_match(2, FollowerBot, NoisyFollowerBot)[1]
    assert a != b


def test_bot_seeds_are_2s_plus_1_and_2s_plus_2():
    seeds = []

    def factory(seed):
        seeds.append(seed)
        return StayBot(seed)

    pe.play_match(10, factory, factory)
    assert seeds == [21, 22]


def test_replay_reproduces_every_tick():
    seed = 31
    match, commands = pe.play_match(seed, NoisyFollowerBot, FollowerBot)
    assert trace_digest(seed, commands) == trace_digest(seed, commands)
    replayed = pe.replay(seed, commands)
    assert repr_floats(replayed.snapshot()) == repr_floats(match.snapshot())
    assert replayed.rallies == match.rallies


def test_replay_of_recorded_match():
    """Partida grabada en disco: semilla + comandos → mismo estado, float a float."""
    golden = json.loads(Path(GOLDEN_PATH).read_text())
    assert golden["engine_version"] == pe.ENGINE_VERSION
    commands = decode_commands(golden["commands"])
    assert len(commands) == golden["ticks"]
    replayed = pe.replay(golden["seed"], commands)
    assert repr_floats(replayed.snapshot()) == golden["final_state"]
    assert replayed.rallies == golden["rallies"]
    assert trace_digest(golden["seed"], commands) == golden["trace_sha256"]


def test_recording_is_reproducible_from_bots():
    # Volver a jugar con los mismos bots y la misma semilla da la misma grabación.
    golden = json.loads(Path(GOLDEN_PATH).read_text())
    assert record_golden() == golden


def test_matches_terminate_within_bound():
    for seed in range(10):
        m, commands = pe.play_match(seed, FollowerBot, FollowerBot)
        assert m.over and len(commands) <= pe.MAX_MATCH_TICKS


# --- restricción aritmética del motor ---------------------------------------------

ENGINE_SOURCE = Path(pe.__file__).read_text()
ALLOWED_MATH = {"sqrt", "floor"}
ALLOWED_IMPORTS = {"math", "random", "__future__", "typing"}
ALLOWED_BUILTINS = {
    "abs",
    "min",
    "max",
    "isinstance",
    "str",
    "dict",
    "list",
    "tuple",
    "RuntimeError",
    "range",
    "len",
    "int",
    "float",
    "Exception",
}


def test_engine_imports_only_allowed_modules():
    tree = ast.parse(ENGINE_SOURCE)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert {a.name for a in node.names} <= ALLOWED_IMPORTS
        if isinstance(node, ast.ImportFrom):
            assert node.module in ALLOWED_IMPORTS


def test_engine_uses_only_allowed_math():
    tree = ast.parse(ENGINE_SOURCE)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == "math":
                assert node.attr in ALLOWED_MATH, node.attr
            if node.value.id == "random":
                assert node.attr == "Random", node.attr
        assert not isinstance(node, ast.Pow), "** no está permitido"
        if isinstance(node, ast.BinOp):
            assert not isinstance(node.op, (ast.FloorDiv, ast.MatMult)), type(node.op)


def test_engine_calls_only_allowed_builtins():
    tree = ast.parse(ENGINE_SOURCE)
    defined = {
        n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))
    }
    defined |= {"left_factory", "right_factory"}  # parámetros de play_match
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id in ALLOWED_BUILTINS | defined, node.func.id


def test_engine_rng_only_uses_random():
    # Todos los sorteos usan random() (no uniform, choice, ...): independiente
    # de detalles de implementación de random entre versiones.
    tree = ast.parse(ENGINE_SOURCE)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute):
            if node.value.attr == "rng":
                assert node.attr in {"random"}, node.attr
