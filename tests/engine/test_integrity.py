"""El motor de la plantilla no se ha modificado (el motor es único)."""

import hashlib
from pathlib import Path

from pong import pong_engine as pe

ENGINE_SHA256 = "8eaba9def843e369fb9165aa46742f7ed71f6be3dcdbf8614db57b631ed288df"


def test_engine_unmodified() -> None:
    data = Path(pe.__file__).read_bytes()
    assert hashlib.sha256(data).hexdigest() == ENGINE_SHA256, (
        "pong_engine.py no coincide con el publicado: restáuralo con "
        "'git checkout -- src/pong/pong_engine.py'"
    )


def test_engine_version() -> None:
    assert pe.ENGINE_VERSION == "1.0"
