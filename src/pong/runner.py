"""Juega una partida de tu bot contra un rival y guarda sus registros.

Enunciado de la práctica, apartado 4.

La partida se juega entera aunque tu bot sea lento: aquí no se aplica el
límite de tiempo medio (enunciado, apartado 3.4), solo se avisa. ``evaluate``
sí lo aplica.

Ejemplos::

    uv run python -m pong.runner --rival easy --semilla 1
    uv run python -m pong.runner --rival hard --lado derecha --csv
    uv run python -m pong.runner --rival mi_bot      # tu bot contra sí mismo
"""

from __future__ import annotations

import argparse
import random
import sys
import traceback
from pathlib import Path

from pong import pong_engine as pe
from pong.bots_ref import NOMBRES, rival
from pong.normas import RUTA_BOT, comprobar_bot, comprobar_clase
from pong.registro import (
    AVISO_MEDIA_MS,
    LIMITE_MEDIA_MS,
    guardar_csv,
    guardar_json,
    jugar_partida,
)


def cargar_mi_bot():
    """Importa ``pong.bot.Bot`` e informa con claridad si falla.

    Antes comprueba que ``bot.py`` cumple las normas (solo los módulos
    permitidos, nada de los bots de referencia ni del motor); si no, no juega.
    """
    if RUTA_BOT.exists():
        problemas = comprobar_bot(RUTA_BOT)
        if problemas:
            print("Tu bot (src/pong/bot.py) no cumple las normas (README, apartado 4):")
            for problema in problemas:
                print(f"  {problema}")
            sys.exit("No se juega ninguna partida hasta que lo corrijas.")
    try:
        from pong.bot import Bot
    except Exception:
        traceback.print_exc()
        sys.exit("No se pudo importar tu bot (src/pong/bot.py).")
    problemas = comprobar_clase(Bot)
    if problemas:
        sys.exit(f"Tu bot no cumple las normas: {problemas[0]}.")
    return Bot


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--rival", default="easy", choices=[*NOMBRES, "mi_bot"])
    p.add_argument(
        "--semilla",
        type=int,
        default=None,
        help="semilla de la partida (por defecto, aleatoria)",
    )
    p.add_argument(
        "--lado",
        choices=["izquierda", "derecha"],
        default="izquierda",
        help="lado de tu bot",
    )
    p.add_argument("--salida", type=Path, default=Path("partidas"))
    p.add_argument(
        "--csv",
        action="store_true",
        help="escribir también el CSV (pesado: unos 135 bytes por tick)",
    )
    a = p.parse_args(argv)

    semilla = (
        a.semilla if a.semilla is not None else random.SystemRandom().randrange(10**9)
    )
    mi_bot = cargar_mi_bot()
    otro = mi_bot if a.rival == "mi_bot" else rival(a.rival)
    if a.lado == "izquierda":
        fabricas, nombres, mi_lado = (mi_bot, otro), ("mi_bot", a.rival), "left"
    else:
        fabricas, nombres, mi_lado = (otro, mi_bot), (a.rival, "mi_bot"), "right"

    partida = jugar_partida(semilla, *fabricas, nombres, filas=a.csv, cronometrar=True)
    base = a.salida / f"partida_{semilla}"
    rutas = [guardar_json(partida, base.with_suffix(".json"))]
    if a.csv:
        rutas.append(guardar_csv(partida, base.with_suffix(".csv")))

    if partida.abandono:
        print(
            f"El constructor del bot de la {partida.abandono} falló: pierde sin jugar."
        )
    m = partida.match
    ganados, jugados = partida.puntos(mi_lado)
    mio = pe.LEFT if mi_lado == "left" else pe.RIGHT
    res = partida.resultado
    if res == "draw":
        texto = "empate técnico"
    else:
        texto = "ganas" if res == mi_lado else "pierdes"
    print(f"Semilla {semilla}: {nombres[0]} (izq.) contra {nombres[1]} (der.)")
    print(
        f"Resultado: {texto}, sets {m.sets[mio]}-{m.sets[1 - mio]}; "
        f"puntos {ganados}/{jugados}; ticks {m.tick}; nulos {m.lets}"
    )
    crono = partida.cronos[0 if mi_lado == "left" else 1]
    print(
        f"Tu bot: {crono.media_ms:.4f} ms por llamada de media; "
        f"máximo {1000 * crono.maximo:.1f} ms"
    )
    if crono.media_ms > LIMITE_MEDIA_MS:
        print(
            f"AVISO: la media supera {LIMITE_MEDIA_MS:.0f} ms; en la evaluación "
            "esta partida se cortaría y la perderías."
        )
    elif crono.media_ms > AVISO_MEDIA_MS:
        print(
            f"AVISO: la media supera {AVISO_MEDIA_MS:.0f} ms (límite: "
            f"{LIMITE_MEDIA_MS:.0f} ms); deja margen para la evaluación oficial."
        )
    for ruta in rutas:
        print(f"Registro: {ruta}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
