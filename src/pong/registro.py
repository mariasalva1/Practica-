"""Partidas con registro: juego, cronometraje y ficheros CSV y JSON.

Enunciado de la práctica, apartado 4.

El motor no escribe ficheros; este módulo sí. Los registros usan
coordenadas globales, no normalizadas.

El JSON basta para reproducir una partida. El CSV, mucho más pesado, se
puede regenerar exactamente a partir del JSON con :func:`csv_desde_json`::

    uv run python -m pong.registro partidas/partida_123.json

El CSV contiene solo lo observable, lo mismo que ven los bots: las
posiciones, los comandos, quién saca y los golpes. Las velocidades y el
efecto, que el motor conoce pero los bots no, son la «verdad» de la partida:
se obtienen aparte con :func:`verdad` o con la opción ``--verdad``, que
escribe ``partida_<seed>_verdad.csv``.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from pong import pong_engine as pe

ORDEN = ("UP", "STAY", "DOWN")
# Columnas observables: lo que ven los bots, en coordenadas globales.
COLUMNAS_CSV = (
    "tick",
    "state",
    "ball_x",
    "ball_y",
    "p_left",
    "p_right",
    "cmd_left",
    "cmd_right",
    "server",
    "rally_hits",
)
# «Verdad» de la partida: estado interno del motor que los bots no reciben.
COLUMNAS_VERDAD = (
    "tick",
    "ball_vx",
    "ball_vy",
    "ball_ay",
    "ball_speed",
)


def fila_csv(snapshot: dict, cmd_izq: str, cmd_der: str) -> tuple:
    """Fila del CSV para un tick: estado antes del tick y sus comandos.

    Args:
        snapshot: resultado de ``Match.snapshot()`` antes de ``step``.
        cmd_izq: comando aplicado por el bot izquierdo en ese tick.
        cmd_der: comando aplicado por el bot derecho en ese tick.

    Returns:
        Una tupla con los valores de :data:`COLUMNAS_CSV`, en ese orden.
    """
    s = snapshot
    return (
        s["tick"],
        s["state"],
        s["ball_x"],
        s["ball_y"],
        s["p_left"],
        s["p_right"],
        cmd_izq,
        cmd_der,
        s["server"],
        s["rally_hits"],
    )


def fila_verdad(snapshot: dict) -> tuple:
    """Fila de la «verdad» de un tick: velocidades y efecto internos del motor.

    Args:
        snapshot: resultado de ``Match.snapshot()`` antes de ``step``.

    Returns:
        Una tupla con los valores de :data:`COLUMNAS_VERDAD`, en ese orden.
    """
    s = snapshot
    return (s["tick"], s["ball_vx"], s["ball_vy"], s["ball_ay"], s["ball_speed"])


def codificar_comandos(comandos: list[tuple[str, str]]) -> str:
    """Un dígito por tick: 3·i + j, con i, j los índices en (UP, STAY, DOWN)."""
    return "".join(str(3 * ORDEN.index(a) + ORDEN.index(b)) for a, b in comandos)


def decodificar_comandos(texto: str) -> list[tuple[str, str]]:
    """Inversa de :func:`codificar_comandos`."""
    return [(ORDEN[int(c) // 3], ORDEN[int(c) % 3]) for c in texto]


# Límites de tiempo (enunciado, apartado 3.4). El motor no los aplica: medir
# tiempos rompería el determinismo. Los aplican la evaluación oficial y ``evaluate.py``.
LIMITE_LLAMADA_S = 0.050  # una llamada más lenta cuenta como STAY (evaluación oficial)
LIMITE_MEDIA_MS = 2.0  # media de la partida; si se supera, la partida se pierde
AVISO_MEDIA_MS = 1.0  # recomendación: no pasar de esta media en local
LLAMADAS_CORTE = 5000  # desde aquí se vigila la media para cortar la partida


@dataclass
class Cronometro:
    """Tiempos de ``decide`` de un bot, en segundos."""

    llamadas: int = 0
    total: float = 0.0
    maximo: float = 0.0
    lentas: int = 0  # llamadas de más de 50 ms

    def anotar(self, segundos: float) -> None:
        """Añade el tiempo de una llamada a ``decide``."""
        self.llamadas += 1
        self.total += segundos
        self.maximo = max(self.maximo, segundos)
        if segundos > LIMITE_LLAMADA_S:
            self.lentas += 1

    def excede(self, limite_ms: float) -> bool:
        """``True`` si la media por llamada supera ``limite_ms``."""
        return 1000.0 * self.total > limite_ms * self.llamadas

    @property
    def media_ms(self) -> float:
        """Media por llamada, en milisegundos."""
        return 1000.0 * self.total / self.llamadas if self.llamadas else 0.0


@dataclass
class Partida:
    """Resultado de :func:`jugar_partida`."""

    seed: int
    nombres: tuple[str, str]
    match: pe.Match
    comandos: list[tuple[str, str]]
    filas: list[tuple] = field(default_factory=list)
    cronos: tuple[Cronometro, Cronometro] = field(
        default_factory=lambda: (Cronometro(), Cronometro())
    )
    abandono: str | None = None  # lado cuyo constructor falló
    tiempo_excedido: str | None = None  # lado que superó la media de tiempo

    @property
    def perdedor_forzoso(self) -> str | None:
        """Lado que pierde sin terminar la partida (abandono o tiempo), o ``None``."""
        return self.abandono if self.abandono is not None else self.tiempo_excedido

    @property
    def resultado(self) -> str:
        """``"left"``, ``"right"`` o ``"draw"``."""
        if self.perdedor_forzoso is not None:
            return "right" if self.perdedor_forzoso == "left" else "left"
        return self.match.result

    def puntos(self, lado: str) -> tuple[int, int]:
        """Puntos ganados por ``lado`` y puntos jugados.

        En una partida perdida por abandono o por tiempo no hay puntos que
        contar: devuelve ``(0, 0)``.
        """
        if self.perdedor_forzoso is not None:
            return 0, 0
        jugados = [r for r in self.match.rallies if r["outcome"] == "point"]
        return sum(1 for r in jugados if r["winner"] == lado), len(jugados)


def _decidir(bot: object, estado: dict, crono: Cronometro | None) -> str:
    if crono is None:
        return pe.ask_bot(bot, estado)
    t0 = time.perf_counter()
    comando = pe.ask_bot(bot, estado)
    crono.anotar(time.perf_counter() - t0)
    return comando


def jugar_partida(
    seed: int,
    izquierda: Callable[[int], object],
    derecha: Callable[[int], object],
    nombres: tuple[str, str] = ("izquierda", "derecha"),
    *,
    filas: bool = False,
    cronometrar: bool = False,
    limite_media_ms: float | None = None,
) -> Partida:
    """Juega una partida completa (semillas de los bots: 2·seed + 1 y 2·seed + 2).

    Si el constructor de un bot falla, la partida no se juega y ese bot pierde.
    Con ``filas=True`` guarda una fila del CSV por tick; con
    ``cronometrar=True`` mide los tiempos de ``decide``. Medir tiempos no
    altera la partida: lo que se graba son los comandos aplicados.

    Con ``limite_media_ms`` (implica ``cronometrar``) se aplica el límite de
    tiempo medio (enunciado, apartado 3.4): desde la llamada
    :data:`LLAMADAS_CORTE` de un bot, en cuanto su media supera el límite, la
    partida se corta y ese bot pierde; al final se comprueba también la media
    de toda la partida. El lado que lo supera queda en ``tiempo_excedido``; si
    lo superan los dos a la vez, pierde el izquierdo.
    """
    cronometrar = cronometrar or limite_media_ms is not None
    match = pe.Match(seed)
    partida = Partida(seed=seed, nombres=nombres, match=match, comandos=[])
    bots = []
    for lado, fabrica, semilla in (
        ("left", izquierda, 2 * seed + 1),
        ("right", derecha, 2 * seed + 2),
    ):
        try:
            bots.append(fabrica(semilla))
        except Exception:
            partida.abandono = lado
            return partida
    crono_izq, crono_der = partida.cronos if cronometrar else (None, None)
    while not match.over:
        c_izq = _decidir(bots[0], match.state_for(pe.LEFT), crono_izq)
        c_der = _decidir(bots[1], match.state_for(pe.RIGHT), crono_der)
        if filas:
            partida.filas.append(fila_csv(match.snapshot(), c_izq, c_der))
        partida.comandos.append((c_izq, c_der))
        match.step(c_izq, c_der)
        if limite_media_ms is not None and crono_izq.llamadas >= LLAMADAS_CORTE:
            partida.tiempo_excedido = _excedido(partida.cronos, limite_media_ms)
            if partida.tiempo_excedido is not None:
                return partida
    if limite_media_ms is not None:
        partida.tiempo_excedido = _excedido(partida.cronos, limite_media_ms)
    return partida


def _excedido(cronos: tuple[Cronometro, Cronometro], limite_ms: float) -> str | None:
    """Lado cuya media supera ``limite_ms`` (primero el izquierdo), o ``None``."""
    for lado, crono in zip(("left", "right"), cronos, strict=True):
        if crono.excede(limite_ms):
            return lado
    return None


def guardar_csv(partida: Partida, ruta: Path) -> Path:
    """Escribe ``partida_<seed>.csv``: una fila por tick."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(COLUMNAS_CSV)
        escritor.writerows(partida.filas)
    return ruta


def guardar_json(partida: Partida, ruta: Path) -> Path:
    """Escribe ``partida_<seed>.json`` con los comandos codificados.

    Una partida cortada por tiempo se graba hasta el tick del corte:
    sus comandos no la terminan y ``tiempo_excedido`` indica quién la perdió.
    """
    m = partida.match
    datos = {
        "engine_version": pe.ENGINE_VERSION,
        "seed": partida.seed,
        "bots": {"left": partida.nombres[0], "right": partida.nombres[1]},
        "sets": {"left": m.sets[pe.LEFT], "right": m.sets[pe.RIGHT]},
        "result": partida.resultado,
        "abandono": partida.abandono,
        "tiempo_excedido": partida.tiempo_excedido,
        "rallies": m.rallies,
        "commands": codificar_comandos(partida.comandos),
    }
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    return ruta


def _leer_registro(ruta: Path) -> dict:
    """Lee un registro JSON y comprueba la versión del motor.

    Raises:
        ValueError: si el registro es de otra versión del motor.
    """
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    if datos["engine_version"] != pe.ENGINE_VERSION:
        raise ValueError(
            f"registro de la versión {datos['engine_version']}; "
            f"el motor es la {pe.ENGINE_VERSION}"
        )
    return datos


def reproducir(ruta: Path) -> pe.Match:
    """Reproduce una partida grabada con el motor, sin el código de los bots."""
    datos = _leer_registro(ruta)
    return pe.replay(datos["seed"], decodificar_comandos(datos["commands"]))


def _rejugar(datos: dict) -> Iterator[tuple[dict, str, str]]:
    """Rejuega un registro: para cada tick, el estado antes del tick y sus comandos."""
    match = pe.Match(datos["seed"])
    for c_izq, c_der in decodificar_comandos(datos["commands"]):
        yield match.snapshot(), c_izq, c_der
        match.step(c_izq, c_der)


def verdad(ruta_json: Path) -> list[dict]:
    """La «verdad» de una partida guardada: vx, vy, ay y s del motor en cada tick.

    Rejuega la partida con el motor a partir de su registro JSON. Sirve para
    comprobar las estimaciones de tu análisis o de tu bot, que solo ven las
    posiciones. Con pandas: ``pd.DataFrame(verdad(ruta))``.

    Args:
        ruta_json: registro ``partida_<seed>.json``.

    Returns:
        Una lista con un diccionario por tick, con las claves de
        :data:`COLUMNAS_VERDAD`. El tick ``t`` corresponde a la fila ``t`` del
        CSV; ``ball_vy`` es la velocidad con la que la bola llegó a la ordenada
        de esa fila (y_t − y_(t−1) = vy_t, salvo rebotes, golpes y redondeo).

    Raises:
        ValueError: si el registro es de otra versión del motor.
    """
    datos = _leer_registro(Path(ruta_json))
    return [
        dict(zip(COLUMNAS_VERDAD, fila_verdad(s), strict=True))
        for s, _, _ in _rejugar(datos)
    ]


def verdad_csv(ruta_json: Path, ruta_csv: Path | None = None) -> Path:
    """Escribe la «verdad» de una partida en ``partida_<seed>_verdad.csv``.

    Args:
        ruta_json: registro ``partida_<seed>.json``.
        ruta_csv: fichero de salida; por defecto, junto al JSON.

    Returns:
        La ruta del CSV escrito.
    """
    ruta_json = Path(ruta_json)
    if ruta_csv is None:
        ruta_csv = ruta_json.with_name(f"{ruta_json.stem}_verdad.csv")
    datos = _leer_registro(ruta_json)
    ruta_csv = Path(ruta_csv)
    ruta_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta_csv, "w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(COLUMNAS_VERDAD)
        for s, _, _ in _rejugar(datos):
            escritor.writerow(fila_verdad(s))
    return ruta_csv


def csv_desde_json(ruta_json: Path, ruta_csv: Path | None = None) -> Path:
    """Regenera el CSV de una partida a partir de su registro JSON.

    Rejuega la partida con el motor a partir de la semilla y los comandos
    grabados, así que el CSV es idéntico, byte a byte, al que habría escrito
    :func:`guardar_csv` al jugarla. Una partida no jugada por abandono
    da un CSV con solo la cabecera.

    Args:
        ruta_json: registro ``partida_<seed>.json``.
        ruta_csv: fichero de salida; por defecto, el mismo nombre con ``.csv``.

    Returns:
        La ruta del CSV escrito.

    Raises:
        ValueError: si el registro es de otra versión del motor.
    """
    ruta_json = Path(ruta_json)
    ruta_csv = ruta_json.with_suffix(".csv") if ruta_csv is None else Path(ruta_csv)
    datos = _leer_registro(ruta_json)
    ruta_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta_csv, "w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(COLUMNAS_CSV)
        for s, c_izq, c_der in _rejugar(datos):
            escritor.writerow(fila_csv(s, c_izq, c_der))
    return ruta_csv


def main(argv: list[str] | None = None) -> int:
    """Orden ``python -m pong.registro``: regenera el CSV de registros JSON."""
    p = argparse.ArgumentParser(
        prog="python -m pong.registro",
        description="Regenera el CSV de partidas guardadas en JSON.",
    )
    p.add_argument("registros", nargs="+", type=Path, help="ficheros partida_*.json")
    p.add_argument(
        "--verdad",
        action="store_true",
        help="escribir también partida_<seed>_verdad.csv (vx, vy, ay y s del motor)",
    )
    a = p.parse_args(argv)
    for ruta in a.registros:
        try:
            print(f"CSV: {csv_desde_json(ruta)}")
            if a.verdad:
                print(f"Verdad: {verdad_csv(ruta)}")
        except (OSError, ValueError, KeyError) as e:
            print(f"No se pudo convertir {ruta}: {e}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
