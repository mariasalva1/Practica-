"""Apoyo del notebook de análisis (``notebook/analisis_mo.py``).

Este módulo no lo modificas: lo importa el notebook. Contiene

- lo que usas en tus funciones: la clase :class:`Datos`, :func:`filas_vuelo`
  y :func:`figura_sin_datos`;
- lo que usa el propio notebook para cargar la partida con tus funciones
  L1–L4 (:func:`cargar`, que antes comprueba con
  :func:`comprobar_coherencia` que lo que devuelven es coherente, y
  :func:`resumen`) y para mostrar cada figura aunque esté por hacer o falle
  (:func:`mostrar` y :func:`apartado`).
"""

from __future__ import annotations

import json
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import marimo as mo
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from pong import pong_engine as pe
from pong.registro import verdad

__all__ = [
    "Datos",
    "apartado",
    "cargar",
    "comprobar_coherencia",
    "figura_aviso",
    "figura_sin_datos",
    "filas_vuelo",
    "mostrar",
    "resolver_partida",
    "resumen",
    "texto_resumen",
]

RAIZ = Path(__file__).resolve().parents[2]  # raíz del repositorio


@dataclass
class Datos:
    """Todo lo que necesitan las figuras de una partida (lo construye :func:`cargar`).

    Attributes:
        ruta: registro JSON de la partida.
        meta: metadatos (L1).
        intercambios: un intercambio por fila (L1).
        ticks: todas las filas del CSV (L2).
        juego: solo las filas ``playing``, con su intercambio (L3).
        vuelos: un vuelo por fila (L4).
        verdad: velocidades reales del motor en cada tick (para P4).
        pendiente: texto que explica qué falta para poder dibujar, o ``None``.
    """

    ruta: Path
    meta: dict | None = None
    intercambios: pd.DataFrame | None = None
    ticks: pd.DataFrame | None = None
    juego: pd.DataFrame | None = None
    vuelos: pd.DataFrame | None = None
    verdad: pd.DataFrame | None = None
    pendiente: str | None = None

    def nombre(self, lado: str) -> str:
        """Nombre del bot de un lado (``"left"`` o ``"right"``)."""
        return self.meta["bots"][lado]


def filas_vuelo(d: Datos, v) -> slice:
    """Filas de ``d.juego`` de un vuelo ``v`` (una fila de ``d.vuelos``).

    Úsala así: ``d.juego["ball_y"].to_numpy()[filas_vuelo(d, v)]``.
    """
    inicio = int(np.searchsorted(d.juego["tick"].to_numpy(), v.tick_ini))
    return slice(inicio, inicio + int(v.n_ticks))


def figura_aviso(texto: str, color: str = "0.35") -> plt.Figure:
    """Figura que solo muestra un texto (pendiente, error o sin datos)."""
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    ax.axis("off")
    ax.text(
        0.5,
        0.5,
        texto,
        ha="center",
        va="center",
        wrap=True,
        fontsize=10,
        color=color,
        family="monospace",
    )
    return fig


def figura_sin_datos(titulo: str) -> plt.Figure:
    """Devuélvela cuando una figura no tenga datos que dibujar."""
    return figura_aviso(f"{titulo}\n\nSin datos en esta partida")


def _registro_en_linea_de_ordenes() -> str | None:
    """La ruta de ``--registro`` si el notebook se ejecuta con ella."""
    try:
        return mo.cli_args().get("registro")
    except Exception:  # fuera de marimo (tests, scripts) no hay argumentos
        return None


def resolver_partida(partida: Path | str) -> tuple[Path | None, str | None]:
    """Ruta del registro que se va a analizar y, si no vale, el motivo.

    Si el notebook se ejecuta con ``-- --registro <ruta>`` (así lo ejecuta el
    profesor), esa ruta sustituye a ``partida``. Una ruta relativa se busca
    desde la carpeta actual y, si no está, desde la raíz del repositorio.

    Returns:
        ``(ruta, None)`` si es un registro JSON de partida de esta versión del
        motor; ``(None, motivo)`` si no lo es.
    """
    ruta = Path(_registro_en_linea_de_ordenes() or partida)
    if not ruta.is_absolute() and not ruta.exists() and (RAIZ / ruta).exists():
        ruta = RAIZ / ruta
    if not ruta.exists():
        return None, f"No existe el fichero {ruta}"
    if ruta.suffix != ".json":
        return None, f"{ruta.name} no es un registro JSON (.json) de partida"
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return None, f"No se puede leer {ruta.name} como JSON: {error}"
    if not isinstance(datos, dict) or not {"seed", "rallies", "commands"} <= set(datos):
        return None, f"{ruta.name} no es un registro de partida de Pong"
    if datos.get("engine_version") != pe.ENGINE_VERSION:
        return None, (
            f"{ruta.name} es de la versión {datos.get('engine_version')} del "
            f"motor; el motor es la {pe.ENGINE_VERSION}"
        )
    return ruta, None


COLUMNAS = {
    "intercambios": [
        "intercambio",
        "start_tick",
        "end_tick",
        "hits",
        "outcome",
        "winner",
    ],
    "ticks": [
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
    ],
    "vuelos": [
        "vuelo",
        "intercambio",
        "golpes",
        "tick_ini",
        "tick_fin",
        "n_ticks",
        "receptor",
        "final",
    ],
}
COLUMNAS["juego"] = [*COLUMNAS["ticks"], "intercambio", "nulo"]
CLAVES_META = {"semilla", "bots", "sets", "resultado", "abandono", "tiempo_excedido"}


def comprobar_coherencia(
    meta: dict,
    intercambios: pd.DataFrame,
    ticks: pd.DataFrame,
    juego: pd.DataFrame,
    vuelos: pd.DataFrame,
) -> None:
    """Comprueba que lo que devuelven L1–L4 es coherente.

    La llama :func:`cargar`; si falla, no se carga la partida. Comprueba que
    las tablas tienen las columnas pedidas, en orden, y que el CSV y el JSON
    cuentan lo mismo: no hay valores nulos en ``juego``; sus filas son
    ``playing`` y sus ticks, consecutivos dentro de cada intercambio; cada
    intercambio terminado en punto tiene ``hits + 1`` vuelos y su mayor
    ``rally_hits`` es ``hits``; cada nulo (se declara en el mismo tick del
    golpe número 100) tiene ``hits`` vuelos y su mayor ``rally_hits`` es
    ``hits − 1``; los intercambios terminados en punto tienen ganador y los
    nulos no; y los receptores de vuelos consecutivos de un intercambio se
    alternan.

    Raises:
        AssertionError: con la primera incoherencia encontrada.
    """
    assert isinstance(meta, dict), "L1: meta no es un diccionario"
    faltan = CLAVES_META - set(meta)
    assert not faltan, f"L1: a meta le faltan las claves {sorted(faltan)}"
    for nombre, tabla in (
        ("L1: intercambios", intercambios),
        ("L2: ticks", ticks),
        ("L3: juego", juego),
        ("L4: vuelos", vuelos),
    ):
        esperadas = COLUMNAS[nombre.split()[-1]]
        assert isinstance(tabla, pd.DataFrame), f"{nombre} no es un DataFrame"
        assert list(tabla.columns) == esperadas, (
            f"{nombre} tiene las columnas {list(tabla.columns)}; deben ser {esperadas}"
        )
    assert not juego.isna().any().any(), "L3: hay valores nulos en juego"
    if juego.empty:
        return
    assert (juego["state"] == "playing").all(), "L3: juego tiene filas no playing"
    saltos = juego.groupby("intercambio")["tick"].diff().dropna()
    assert (saltos == 1).all(), "L3: ticks no consecutivos dentro de un intercambio"
    assert set(juego["intercambio"]) <= set(intercambios["intercambio"]), (
        "L3: juego tiene intercambios que no están en intercambios"
    )
    assert set(vuelos["intercambio"]) == set(juego["intercambio"]), (
        "L4: los intercambios de vuelos no son los de juego"
    )
    por_intercambio = vuelos.groupby("intercambio").size()
    maximo = juego.groupby("intercambio")["rally_hits"].max()
    tabla = intercambios.set_index("intercambio").loc[por_intercambio.index]
    esperados = tabla["hits"] + (tabla["outcome"] == "point").astype(int)
    assert (por_intercambio == esperados).all(), (
        "L4: número de vuelos de algún intercambio distinto del esperado"
    )
    assert (maximo.loc[esperados.index] == esperados - 1).all(), (
        "L3/L4: el rally_hits máximo de algún intercambio no cuadra con hits"
    )
    es_punto = intercambios["outcome"] == "point"
    assert (es_punto == intercambios["winner"].notna()).all(), (
        "L1: un punto sin ganador o un nulo con ganador"
    )
    mismo = vuelos["intercambio"].eq(vuelos["intercambio"].shift())
    alterna = vuelos["receptor"].ne(vuelos["receptor"].shift())
    assert alterna[mismo].all(), (
        "L4: receptores de vuelos consecutivos que no se alternan"
    )


def cargar(
    partida: Path | str,
    leer_registro: Callable,
    leer_ticks: Callable,
    limpiar: Callable,
    vuelos: Callable,
) -> Datos:
    """Construye los :class:`Datos` de una partida con tus funciones L1–L4.

    Comprueba antes la ruta (ver :func:`resolver_partida`). Si la ruta no
    vale, si alguna de L1–L4 está por hacer o falla, o si lo que devuelven
    no es coherente (:func:`comprobar_coherencia`), se detiene y lo anota en
    ``pendiente``: las figuras lo muestran en lugar de dibujarse.
    """
    ruta, motivo = resolver_partida(partida)
    d = Datos(ruta=Path(partida) if ruta is None else ruta)
    if motivo is not None:
        d.pendiente = f"Partida no válida: {motivo}"
        return d
    pasos = [
        ("L1", lambda: leer_registro(d.ruta)),
        ("L2", lambda: leer_ticks(d.ruta)),
        ("L3", lambda: limpiar(d.ticks, d.intercambios)),
        ("L4", lambda: vuelos(d.juego)),
    ]
    for nombre, paso in pasos:
        try:
            resultado = paso()
        except NotImplementedError:
            d.pendiente = f"Pendiente: completa {nombre}"
            return d
        except Exception:
            d.pendiente = f"Error en {nombre}:\n" + traceback.format_exc(limit=3)
            return d
        if nombre == "L1":
            try:
                d.meta, d.intercambios = resultado
            except (TypeError, ValueError):
                d.pendiente = "Error en L1: debe devolver (meta, intercambios)"
                return d
        elif nombre == "L2":
            d.ticks = resultado
        elif nombre == "L3":
            d.juego = resultado
        else:
            d.vuelos = resultado
    try:
        comprobar_coherencia(d.meta, d.intercambios, d.ticks, d.juego, d.vuelos)
    except AssertionError as error:
        d.pendiente = (
            "Los datos de L1–L4 no son coherentes, no se carga la partida:\n"
            f"{error or 'falla una comprobación'}"
        )
        return d
    except Exception as error:
        d.pendiente = (
            "Los datos de L1–L4 no son coherentes, no se carga la partida:\n"
            f"{type(error).__name__}: {error}"
        )
        return d
    d.verdad = pd.DataFrame(verdad(d.ruta))
    return d


def texto_resumen(d: Datos) -> str:
    """Resumen de la partida cargada, en Markdown."""
    if d.pendiente:
        return "**Partida:** " + d.pendiente.replace("\n", "  \n")
    texto = (
        f"**Partida** `{d.ruta.name}`: semilla {d.meta['semilla']}, "
        f"{d.nombre('left')} (izq.) contra {d.nombre('right')} (der.); "
        f"{len(d.ticks)} ticks, {len(d.intercambios)} intercambios y "
        f"{len(d.vuelos)} vuelos. Datos de L1–L4 coherentes ✔"
    )
    return texto


def resumen(d: Datos):
    """Resumen de la partida cargada, para mostrarlo."""
    return mo.md(texto_resumen(d))


def mostrar(funcion: Callable[[Datos], plt.Figure], d: Datos):
    """Dibuja ``funcion(d)``; si está pendiente o falla, lo indica en su lugar.

    Returns:
        La figura convertida a HTML de marimo (la figura se cierra).
    """
    if d.pendiente is not None:
        fig = figura_aviso(d.pendiente)
    else:
        try:
            fig = funcion(d)
        except NotImplementedError:
            fig = figura_aviso(f"Pendiente: completa {funcion.__name__}")
        except Exception:
            fig = figura_aviso(
                f"Error en {funcion.__name__}:\n"
                + traceback.format_exc(limit=3)[-600:],
                color="firebrick",
            )
    html = mo.as_html(fig)
    plt.close(fig)
    return html


def apartado(titulo: str, funcion: Callable[[Datos], plt.Figure], d: Datos):
    """Título y figura (o el aviso de que está pendiente o falla)."""
    return mo.vstack([mo.md(f"#### {titulo}"), mostrar(funcion, d)])
