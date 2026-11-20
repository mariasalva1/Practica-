"""Mide tu porcentaje de puntos contra un bot de referencia (enunciado, apartado 7.1).

Juega N partidas alternando lados, como la evaluación oficial, y estima los
puntos de rendimiento contra ese bot con las cotas publicadas: hasta 1 punto
contra Easy, 1 contra Medium y 1,5 contra Hard, sobre los 10 de la práctica.
El resultado oficial solo difiere del tuyo por el azar de las
semillas.

Ejemplos::

    uv run python -m pong.evaluate --rival medium
    uv run python -m pong.evaluate --rival hard --partidas 100 --semilla-base 1000
    uv run python -m pong.evaluate --rival hard --partidas 20 --guardar

Con ``--guardar``, cada ejecución crea una carpeta propia, por ejemplo
``partidas/evaluate_hard_2026-11-03_1015/``, con el registro JSON de cada
partida (para verla en ``pong.html`` o analizarla) y ``resumen.csv``: una fila
por partida, de la peor a la mejor.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from pong.bots_ref import NOMBRES, rival
from pong.registro import (
    AVISO_MEDIA_MS,
    LIMITE_MEDIA_MS,
    LLAMADAS_CORTE,
    Cronometro,
    guardar_json,
    jugar_partida,
)
from pong.runner import cargar_mi_bot

# Cotas de la rúbrica: porcentaje de puntos para 0 y para todos los puntos.
COTAS: dict[str, tuple[float, float]] = {
    "easy": (0.50, 0.90),
    "medium": (0.45, 0.70),
    "hard": (0.35, 0.48),
}
# Puntos de la nota de la práctica (sobre 10) por cada bot de referencia.
PESOS: dict[str, float] = {"easy": 1.0, "medium": 1.0, "hard": 1.5}


def nota_componente(rival_nombre: str, puntos: float) -> float:
    """Puntos de rendimiento contra un bot de referencia.

    Lineales entre las cotas: 0 con ``puntos`` en la cota inferior o por
    debajo, y ``PESOS[rival_nombre]`` en la superior o por encima.

    Args:
        rival_nombre: ``"easy"``, ``"medium"`` o ``"hard"``.
        puntos: porcentaje de puntos, como fracción entre 0 y 1.
    """
    bajo, alto = COTAS[rival_nombre]
    return PESOS[rival_nombre] * min(1.0, max(0.0, (puntos - bajo) / (alto - bajo)))


COLUMNAS_RESUMEN = (
    "semilla",
    "lado",
    "puntos",
    "ganados",
    "jugados",
    "resultado",
    "ticks",
    "registro",
)
LADOS = {"left": "izquierda", "right": "derecha"}


@dataclass
class PartidaEvaluada:
    """Resultado de una partida de la evaluación, visto desde tu bot."""

    semilla: int
    lado: str  # "left" o "right": lado de tu bot
    ganados: int
    jugados: int
    puntos: float  # fracción de puntos que cuenta para la nota
    resultado: str  # "gana", "pierde", "empate", "abandono" o "tiempo"
    ticks: int


@dataclass
class Resumen:
    victorias: int
    empates: int
    derrotas: int
    puntos: float  # porcentaje de puntos (media por partida)
    error: float  # error típico por partidas
    cronometro: Cronometro
    detalle: list[PartidaEvaluada] = field(default_factory=list)
    por_tiempo: int = 0  # partidas perdidas por superar la media de tiempo

    @property
    def partidas(self) -> int:
        return self.victorias + self.empates + self.derrotas


def evaluar(
    rival_nombre: str, n: int, semilla_base: int, guardar: Path | None = None
) -> Resumen:
    """Juega ``n`` partidas: en semillas pares tu bot juega a la izquierda.

    Aplica el límite de tiempo medio (enunciado, apartado 3.4), como la
    evaluación oficial: si tu bot lo supera, la partida se corta y cuenta 0.

    Args:
        rival_nombre: ``"easy"``, ``"medium"`` o ``"hard"``.
        n: número de partidas.
        semilla_base: semilla de la primera partida; las demás son consecutivas.
        guardar: carpeta donde escribir el JSON de cada partida y
            ``resumen.csv``, o ``None`` para no guardar nada.

    Returns:
        El resumen de la evaluación, con el detalle de cada partida.
    """
    mi_bot = cargar_mi_bot()
    otro = rival(rival_nombre)
    v = e = d = t = 0
    por_partida: list[float] = []
    detalle: list[PartidaEvaluada] = []
    crono = Cronometro()
    for i in range(n):
        seed = semilla_base + i
        if seed % 2 == 0:
            fabricas, nombres, lado = (mi_bot, otro), ("mi_bot", rival_nombre), "left"
        else:
            fabricas, nombres, lado = (otro, mi_bot), (rival_nombre, "mi_bot"), "right"
        partida = jugar_partida(
            seed, *fabricas, nombres, limite_media_ms=LIMITE_MEDIA_MS
        )
        res = partida.resultado
        if res == "draw":
            e += 1
        elif res == lado:
            v += 1
        else:
            d += 1
        ganados, jugados = partida.puntos(lado)
        # Abandono o tiempo excedido: 0 puntos al que lo provoca y
        # todos al otro; empate técnico, 0.5
        if partida.perdedor_forzoso is not None:
            fraccion = 0.0 if partida.perdedor_forzoso == lado else 1.0
        elif res == "draw" and jugados == 0:
            fraccion = 0.5
        else:
            fraccion = ganados / jugados if jugados else 0.0
        por_partida.append(fraccion)
        if partida.abandono is not None:
            texto = "abandono"
        elif partida.tiempo_excedido is not None:
            texto = "tiempo"
            t += partida.tiempo_excedido == lado
        elif res == "draw":
            texto = "empate"
        else:
            texto = "gana" if res == lado else "pierde"
        detalle.append(
            PartidaEvaluada(
                seed, lado, ganados, jugados, fraccion, texto, partida.match.tick
            )
        )
        c = partida.cronos[0 if lado == "left" else 1]
        crono.llamadas += c.llamadas
        crono.total += c.total
        crono.maximo = max(crono.maximo, c.maximo)
        crono.lentas += c.lentas
        if guardar is not None:
            guardar_json(partida, guardar / f"partida_{seed}.json")
    media = sum(por_partida) / n
    error = (
        math.sqrt(sum((x - media) ** 2 for x in por_partida) / (n - 1) / n)
        if n > 1
        else 0.0
    )
    if guardar is not None:
        guardar_resumen(detalle, guardar / "resumen.csv")
    return Resumen(v, e, d, media, error, crono, detalle, t)


def carpeta_ejecucion(salida: Path, rival_nombre: str, momento: datetime) -> Path:
    """Carpeta nueva para guardar una ejecución de ``evaluate``.

    Se llama ``evaluate_<rival>_<fecha>_<hora>``; si ya existe (dos ejecuciones
    en el mismo minuto), se añade ``_2``, ``_3``…
    """
    nombre = f"evaluate_{rival_nombre}_{momento:%Y-%m-%d_%H%M}"
    carpeta = salida / nombre
    k = 2
    while carpeta.exists():
        carpeta = salida / f"{nombre}_{k}"
        k += 1
    return carpeta


def ordenar_peor_a_mejor(detalle: list[PartidaEvaluada]) -> list[PartidaEvaluada]:
    """Partidas ordenadas por fracción de puntos creciente (y por semilla)."""
    return sorted(detalle, key=lambda p: (p.puntos, p.semilla))


def guardar_resumen(detalle: list[PartidaEvaluada], ruta: Path) -> Path:
    """Escribe ``resumen.csv``: una fila por partida, de la peor a la mejor.

    Columnas: semilla, lado de tu bot, fracción de puntos que cuenta para la
    nota, puntos ganados y jugados, resultado, ticks y nombre del registro.
    """
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(COLUMNAS_RESUMEN)
        for p in ordenar_peor_a_mejor(detalle):
            escritor.writerow(
                (
                    p.semilla,
                    LADOS[p.lado],
                    f"{p.puntos:.4f}",
                    p.ganados,
                    p.jugados,
                    p.resultado,
                    p.ticks,
                    f"partida_{p.semilla}.json",
                )
            )
    return ruta


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--rival", required=True, choices=NOMBRES)
    p.add_argument("--partidas", type=int, default=20)
    p.add_argument(
        "--semilla-base",
        type=int,
        default=None,
        help="primera semilla (por defecto, aleatoria)",
    )
    p.add_argument(
        "--guardar",
        action="store_true",
        help="guardar el JSON de cada partida y resumen.csv en una carpeta nueva "
        "dentro de --salida",
    )
    p.add_argument("--salida", type=Path, default=Path("partidas"))
    a = p.parse_args(argv)
    if a.partidas < 2:
        p.error("--partidas debe ser al menos 2")

    base = (
        a.semilla_base
        if a.semilla_base is not None
        else random.SystemRandom().randrange(10**9)
    )
    carpeta = (
        carpeta_ejecucion(a.salida, a.rival, datetime.now()) if a.guardar else None
    )
    r = evaluar(a.rival, a.partidas, base, carpeta)
    bajo, alto = COTAS[a.rival]
    ic = 1.96 * r.error
    print(f"Contra {a.rival}: {r.partidas} partidas desde la semilla {base}")
    print(
        f"  Partidas: {r.victorias} ganadas, {r.empates} empates, {r.derrotas} perdidas"
    )
    print(
        f"  Puntos ganados: {100 * r.puntos:.1f} % "
        f"(IC 95 %: {100 * (r.puntos - ic):.1f}–{100 * (r.puntos + ic):.1f} %)"
    )
    print(
        f"  Cotas de la rúbrica: 0 puntos con {100 * bajo:.0f} % o menos, "
        f"todos con {100 * alto:.0f} % o más"
    )
    print(
        f"  Nota estimada contra {a.rival}: "
        f"{nota_componente(a.rival, r.puntos):.2f} de {PESOS[a.rival]:g} puntos "
        "(sobre 10 de la práctica)"
    )
    print(
        f"  Tiempo de tu bot: {r.cronometro.media_ms:.4f} ms por llamada de media; "
        f"máximo {1000 * r.cronometro.maximo:.1f} ms"
    )
    if r.por_tiempo:
        print(
            f"  AVISO: {r.por_tiempo} partidas perdidas (0 puntos) porque tu bot "
            f"superó {LIMITE_MEDIA_MS:.0f} ms de media por llamada; se cortan en "
            f"cuanto la media lo supera, a partir de la llamada {LLAMADAS_CORTE}."
        )
    elif r.cronometro.media_ms > AVISO_MEDIA_MS:
        print(
            f"  AVISO: la media supera {AVISO_MEDIA_MS:.0f} ms. El límite es "
            f"{LIMITE_MEDIA_MS:.0f} ms, pero la máquina de la evaluación oficial "
            "puede ser más lenta que la tuya: deja margen."
        )
    if r.cronometro.lentas:
        print(
            f"  AVISO: {r.cronometro.lentas} llamadas superaron 50 ms; "
            "en la evaluación oficial contarían como STAY."
        )
    if carpeta is not None:
        print(f"Registros: {carpeta}/ ({r.partidas} partidas y resumen.csv)")
        print("  Tus peores partidas (ábrelas en pong.html, pestaña Reproducción):")
        for p in ordenar_peor_a_mejor(r.detalle)[:5]:
            print(
                f"    partida_{p.semilla}.json  {LADOS[p.lado]:<9}  "
                f"{100 * p.puntos:5.1f} %  ({p.ganados}/{p.jugados})  {p.resultado}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
