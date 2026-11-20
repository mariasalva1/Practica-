"""Utilidades para grabar y reproducir partidas de referencia.

Regenerar la partida grabada (solo tras un cambio de reglas que incremente
ENGINE_VERSION):

    uv run python tests/engine/golden.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from helpers import FollowerBot, NoisyFollowerBot  # noqa: E402

from pong import pong_engine as pe  # noqa: E402

GOLDEN_SEED = 2026
GOLDEN_PATH = HERE / "data" / f"golden_seed{GOLDEN_SEED}.json"


def repr_floats(value: object) -> object:
    """Sustituye cada float por su repr, recursivamente."""
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, dict):
        return {k: repr_floats(v) for k, v in value.items()}
    if isinstance(value, list):
        return [repr_floats(v) for v in value]
    return value


_ORDER = ("UP", "STAY", "DOWN")


def encode_commands(commands: list[tuple[str, str]]) -> str:
    """Un dígito por tick: 3·i + j, con i, j los índices en (UP, STAY, DOWN)."""
    return "".join(str(3 * _ORDER.index(a) + _ORDER.index(b)) for a, b in commands)


def decode_commands(text: str) -> list[tuple[str, str]]:
    return [(_ORDER[int(ch) // 3], _ORDER[int(ch) % 3]) for ch in text]


def trace_digest(seed: int, commands: list[tuple[str, str]]) -> str:
    """SHA-256 del repr del estado global tras cada tick."""
    h = hashlib.sha256()
    m = pe.Match(seed)
    h.update(repr(repr_floats(m.snapshot())).encode())
    for c_left, c_right in commands:
        m.step(c_left, c_right)
        h.update(repr(repr_floats(m.snapshot())).encode())
    return h.hexdigest()


def record_golden() -> dict:
    match, commands = pe.play_match(GOLDEN_SEED, FollowerBot, NoisyFollowerBot)
    return {
        "engine_version": pe.ENGINE_VERSION,
        "seed": GOLDEN_SEED,
        "bots": ["FollowerBot", "NoisyFollowerBot"],
        "ticks": len(commands),
        "commands": encode_commands(commands),
        "final_state": repr_floats(match.snapshot()),
        "rallies": match.rallies,
        "trace_sha256": trace_digest(GOLDEN_SEED, commands),
    }


if __name__ == "__main__":
    GOLDEN_PATH.parent.mkdir(exist_ok=True)
    GOLDEN_PATH.write_text(json.dumps(record_golden(), separators=(",", ":")))
    print(f"escrito {GOLDEN_PATH}")
