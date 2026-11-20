import marimo

__generated_with = "0.25.0"
app = marimo.App(width="medium", app_title="Análisis de una partida de Pong")

with app.setup:
    # Bibliotecas que puedes usar. No hace falta importar nada más.
    import json  # noqa: F401
    import math  # noqa: F401
    import tempfile  # noqa: F401
    from pathlib import Path

    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd

    from pong import pong_engine as pe
    from pong.analisis import (
        Datos,
        apartado,
        cargar,
        figura_sin_datos,  # noqa: F401
        filas_vuelo,  # noqa: F401
        resumen,
    )
    from pong.registro import csv_desde_json  # noqa: F401

    # Constantes del motor
    R = pe.R  # radio de la bola (px)
    H = pe.H  # alto del campo (px)
    L = pe.L  # recorrido vertical del centro de la bola: H − 2R (px)
    X_IZQ = pe.X_L + pe.R  # plano del centro de la bola en el impacto, izquierda
    X_DER = pe.X_R - pe.R  # plano del centro de la bola en el impacto, derecha
    ALCANCE = pe.HALF_REACH  # semiancho de la franja de impacto: 46 px
    KAPPA = pe.KAPPA  # efecto: a = κ·c (px/tick²)
    LADOS = ("left", "right")
    CARPETA = Path(__file__).parent  # carpeta del notebook

    # Partida que se analiza. Cámbiala por la ruta de cualquier registro JSON,
    # absoluta o relativa a la raíz del repositorio; por ejemplo,
    # PARTIDA = Path("partidas/partida_7.json")
    PARTIDA = CARPETA / "ejemplo.json"


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # Análisis de una partida de Pong

    Este notebook, parte importante de la Práctica, se emplea para analizar **una partida cualquiera** a partir de su registro JSON.

    El **motor** es `src/pong/pong_engine.py`, el módulo que simula el juego. Las reglas completas del juego están en la especificación, en la web de la asignatura.

    - La partida que se analiza es la de la variable `PARTIDA`, en la primera celda del notebook (la de las importaciones). Por defecto es `notebook/ejemplo.json` (Hard contra Medium). Puedes cambiarla por la ruta de cualquier registro JSON, absoluta o relativa a la raíz del repositorio, por ejemplo `PARTIDA = Path("partidas/partida_7.json")`.
    - Debes completar las funciones que se te indican (marcadas con `raise NotImplementedError`).
    - Otras funciones que debes emplear ya están escritas en el módulo `pong.analisis` (**fichero `src/pong/analisis.py`, que no puedes cambiar**) y debes utilizarlas tal como están donde ellas aparecen. **No debes cambiar nada de esas llamadas preestablecidas: los nombres, los parámetros y lo que devuelve cada función forman parte de la evaluación.**
    - La clase `Datos` y las funciones de apoyo `filas_vuelo` y `figura_sin_datos` aparecen también en el módulo `pong.analisis`.
    - Cada figura debe llevar título, ejes con nombre y unidades, y ser del **tipo de gráfico** que se indica en su enunciado. En `notebook/ejemplo.html` tienes este mismo enunciado con las figuras de la solución dibujadas con la partida de ejemplo: compara las tuyas con ellas.
    - **Las funciones de lectura y limpieza (L1–L4) son obligatorias y lo primero que debes hacer:** con ellas se carga la partida, y sin ellas no se dibuja ninguna figura. Además, `cargar` comprueba que lo que devuelven es coherente y, si encuentra alguna inconsistencia, no carga la partida y lo indica en lugar de las figuras.
    - **L1–L4 son un requisito del notebook: si con la partida del profesor, o con alguna de las de sus tests (normales, con nulo, con abandono o cortadas por tiempo), alguna de L1–L4 falla o `cargar` no carga la partida, el notebook se califica con 0** (el notebook debe funcionar con cualquier partida). Compruébalo antes de entregar con `uv run pytest tests/test_notebook.py`, que carga con tus funciones `notebook/ejemplo.json` y las partidas raras de `notebook/raras/` (abandono, con nulo y cortada por tiempo), y analizándolas aquí con `PARTIDA`. Superar ese test no garantiza los 0,4 puntos de L1–L4, que se corrigen con tests propios del profesor.
    - Con la partida cargada, mientras una función de los apartados siguientes esté por hacer o falle, su figura lo indica en su lugar y el resto del notebook sigue funcionando.
    - El profesor ejecutará tu notebook con otra partida, que no has visto, dada en la línea de órdenes (`-- --registro <ruta>`, que sustituye a `PARTIDA`). Tu notebook tiene que funcionar con cualquier partida, también con las raras: abandono, corte por tiempo, un bot sin puntos o partidas con nulos.

    **Puntuación** (4,5 puntos): una base de 3 puntos (lectura y limpieza de datos, L1–L4, 0,4; P1–P4, 0,4 cada una; S1, S2, S5 y S7, 0,25 cada una) y una ampliación de 1,5 puntos (S3, 0,5; S6, 0,4; S4, 0,3; S8, 0,3).
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Lectura y limpieza de datos (0,4 puntos)

    Las cuatro funciones de esta sección son obligatorias y un requisito del notebook (ver la introducción): sin ellas no se puede cargar la partida (ver «Comprobación y carga de la partida», al final de la sección). Todas deben funcionar con partidas de cualquier tipo, por ejemplo, una partida sin ticks (abandono). Se debe tratar de no emplear bucles `for` sobre las filas del CSV (usa operaciones de pandas y NumPy). Los nombres y el orden de las columnas de cada tabla forman parte de la evaluación.

    ### **L1:** `leer_registro(ruta)`

    La función `leer_registro(ruta)` lee el registro JSON de la `ruta` que recibe (en este notebook, `PARTIDA`) y devuelve un diccionario de metadatos `meta` y un `DataFrame` de pandas `intercambios` en el que cada fila resume un **intercambio**.

    **Ejemplo:**

    Con la partida de ejemplo `meta` es:

    ```python
    {
        "semilla": 41,
        "bots": {"left": "hard", "right": "medium"},
        "sets": {"left": 2, "right": 0},
        "resultado": "left",
        "abandono": None,
        "tiempo_excedido": None,
    }
    ```

    donde

    - **`semilla`:** semilla de la partida.
    - **`bots`:** nombre del bot de cada lado. Las figuras lo usan en títulos y leyendas a través de `d.nombre("left")`.
    - **`sets`:** sets ganados por cada lado.
    - **`resultado`:** quién ganó la partida: `"left"`, `"right"` o `"draw"` (empate técnico).
    - **`abandono`:** el lado cuyo bot no pudo construirse, o `None`.
    - **`tiempo_excedido`:** el lado cuyo bot superó el tiempo medio y perdió la partida por corte, o `None`.

    Con la partida de ejemplo las primeras filas de `intercambios` son:

    | intercambio | start_tick | end_tick | hits | outcome | winner |
    | --- | --- | --- | --- | --- | --- |
    | 1 | 0 | 1936 | 24 | point | left |
    | 2 | 1937 | 3842 | 26 | point | left |
    | 3 | 3843 | 5721 | 24 | point | left |
    | 4 | 5722 | 7592 | 24 | point | left |

    donde

    - **`intercambio`:** número de orden (1, 2, …), que añade L1.
    - **`start_tick`:** primer tick del intercambio, que empieza con la pausa del saque.
    - **`end_tick`:** tick en el que se decide el punto o se declara el nulo.
    - **`hits`:** golpes de raqueta en el intercambio.
    - **`outcome`:** `"point"` si terminó en punto, `"let"` si fue nulo.
    - **`winner`:** quién ganó el punto (`"left"` o `"right"`), `None` si fue nulo.
    """)
    return


@app.function
def leer_registro(ruta: Path) -> tuple[dict, pd.DataFrame]:
    """L1. Lee un registro JSON de partida.

    Args:
        ruta: fichero .json que registra una partida.

    Returns:
        meta: diccionario de metadatos.
        intercambios: DataFrame de pandas con un intercambio por fila.
    """
    raise NotImplementedError("Por hacer")


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### **L2:** `leer_ticks(ruta)`

    La función `leer_ticks(ruta)` genera el CSV con `csv_desde_json` en la carpeta temporal del sistema (`tempfile.gettempdir()`), lo lee con pandas y lo devuelve en un `DataFrame`, `ticks`, con una fila por tick y las diez columnas del CSV en el mismo orden. Los tipos de las columnas forman parte de la evaluación: `state`, `cmd_left`, `cmd_right` y `server` de tipo `category`; `tick` y `rally_hits`, enteros (`int64`); y las posiciones `ball_x`, `ball_y`, `p_left` y `p_right`, `float64`.

    **Ejemplo:**

    El CSV de la partida de ejemplo tiene 52 075 filas, una por tick, más la cabecera:

    ```csv
    tick,state,ball_x,ball_y,p_left,p_right,cmd_left,cmd_right,server,rally_hits
    0,serving,400.0,300.0,300.0,300.0,STAY,STAY,left,0
    1,serving,400.0,300.0,300.0,300.0,STAY,STAY,left,0
    ...
    59,serving,400.0,300.0,300.0,300.0,STAY,STAY,left,0
    60,playing,400.0,300.0,300.0,300.0,STAY,STAY,left,0
    61,playing,405.34346665011645,302.72898592138057,300.0,300.0,STAY,DOWN,left,0
    62,playing,410.6869333002329,305.45797184276114,300.0,308.0,STAY,DOWN,left,0
    ...
    127,playing,758.01…,482.84…,300.0,500.0,STAY,STAY,left,0
    128,playing,763.36…,485.57…,300.0,500.0,STAY,STAY,left,0
    129,playing,764.0,485.90…,300.0,500.0,STAY,UP,left,1
    130,playing,758.35…,482.90…,300.0,492.0,UP,UP,left,1
    ```
    """)
    return


@app.function
def leer_ticks(ruta: Path) -> pd.DataFrame:
    """L2. Tabla de ticks de la partida (el CSV observable, una fila por tick).

    Genera el CSV con ``csv_desde_json`` en la carpeta temporal del sistema
    (``tempfile.gettempdir()``) y lo lee con pandas.

    Args:
        ruta: fichero .json que registra una partida.

    Returns:
        ticks: DataFrame de pandas con una fila por tick y las diez columnas
        del CSV, en el mismo orden.
    """
    raise NotImplementedError("Por hacer")


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### **L3:** `limpiar(ticks, intercambios)`

    La función `limpiar(ticks, intercambios)` devuelve un `DataFrame`, `juego`, con las filas de `ticks` cuyo `state` es `"playing"`, y les añade dos columnas:

    - **`intercambio`:** el número del intercambio cuyo intervalo [`start_tick`, `end_tick`] contiene el tick;
    - **`nulo`:** `True` si ese intercambio terminó en nulo y `False` si terminó en punto.

    Las filas que no caen en ningún intercambio (por ejemplo, el final de una partida cortada por tiempo) se descartan. El índice se renumera desde 0.

    **Ejemplo:**

    Con la partida de ejemplo `juego` tiene 50 455 filas (de las 52 075 de `ticks`). Las primeras son:

    | tick | state | ball_x | ball_y | p_left | p_right | cmd_left | cmd_right | server | rally_hits | intercambio | nulo |
    | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
    | 60 | playing | 400.0 | 300.0 | 300.0 | 300.0 | STAY | STAY | left | 0 | 1 | False |
    | 61 | playing | 405.343467 | 302.728986 | 300.0 | 300.0 | STAY | DOWN | left | 0 | 1 | False |
    | 62 | playing | 410.686933 | 305.457972 | 300.0 | 308.0 | STAY | DOWN | left | 0 | 1 | False |
    """)
    return


@app.function
def limpiar(ticks: pd.DataFrame, intercambios: pd.DataFrame) -> pd.DataFrame:
    """L3. Filas en juego, cada una con su intercambio.

    Se queda con las filas cuyo ``state`` es ``"playing"`` y les añade la
    columna ``intercambio`` (el intercambio cuyo intervalo
    [``start_tick``, ``end_tick``] contiene el tick) y la columna booleana
    ``nulo`` (``True`` si ese intercambio terminó en nulo). Las filas que no
    caen en ningún intercambio (por ejemplo, el final de una partida cortada
    por tiempo) se descartan. El índice se renumera desde 0.
    """
    raise NotImplementedError("Por hacer")


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### **L4:** `vuelos(juego)`

    La función `vuelos(juego)` devuelve un `DataFrame` con una fila por vuelo. Un **vuelo** es el tramo de la trayectoria de la bola entre dos golpes consecutivos, desde el saque hasta el primer golpe o desde el último golpe hasta el final del intercambio; los rebotes en las paredes no lo cortan. En el CSV, son las filas consecutivas de un intercambio con el mismo `rally_hits`, que cambia en cada golpe. La fila de un golpe es la primera del vuelo que empieza: en ella la bola está en el plano de impacto (`X_IZQ` o `X_DER`), a la ordenada de impacto $y^*$. Por eso un intercambio terminado en punto tiene `hits + 1` vuelos, y el último termina en la última fila `playing` del intercambio, antes de que la bola cruce el plano de la raqueta.

    **Ejemplo:**

    La partida de ejemplo tiene 716 vuelos: 689 terminan en golpe y 27 en fallo (uno por intercambio; no hay nulos). Los primeros son:

    | vuelo | intercambio | golpes | tick_ini | tick_fin | n_ticks | receptor | final |
    | --- | --- | --- | --- | --- | --- | --- | --- |
    | 0 | 1 | 0 | 60 | 128 | 69 | right | golpe |
    | 1 | 1 | 1 | 129 | 257 | 129 | left | golpe |
    | 2 | 1 | 2 | 258 | 366 | 109 | right | golpe |
    | 3 | 1 | 3 | 367 | 539 | 173 | left | golpe |
    | 4 | 1 | 4 | 540 | 635 | 96 | right | golpe |

    donde

    - **`vuelo`:** número de orden (0, 1, …), en orden de tick.
    - **`intercambio`:** intercambio al que pertenece.
    - **`golpes`:** el `rally_hits` de sus filas (golpes dados antes del vuelo).
    - **`tick_ini`**, **`tick_fin`:** primer y último tick del vuelo.
    - **`n_ticks`:** número de filas del vuelo.
    - **`receptor`:** hacia dónde va la bola: `"left"` si va hacia la izquierda, `"right"` si va hacia la derecha. Si el vuelo tiene un solo tick, va hacia la raqueta más lejana.
    - **`final`:** `"golpe"` si le sigue otro vuelo del mismo intercambio, `"nulo"` si es el último de un intercambio nulo y `"fallo"` si es el último de un intercambio que terminó en punto.
    """)
    return


@app.function
def vuelos(juego: pd.DataFrame) -> pd.DataFrame:
    """L4. Una fila por vuelo.

    Un vuelo agrupa las filas consecutivas de un mismo intercambio con el
    mismo ``rally_hits``.

    Returns:
        Columnas: ``vuelo`` (0, 1, …, en orden de tick), ``intercambio``,
        ``golpes`` (el ``rally_hits`` del vuelo), ``tick_ini``, ``tick_fin``,
        ``n_ticks``, ``receptor`` (``"left"`` si la bola va hacia la
        izquierda, ``"right"`` si va hacia la derecha) y ``final``
        (``"golpe"`` si le sigue otro vuelo del mismo intercambio, ``"nulo"``
        si es el último de un intercambio nulo y ``"fallo"`` si es el último
        de un intercambio que terminó en punto).
    """
    raise NotImplementedError("Por hacer")


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### Comprobación y carga de la partida

    Cuando tengas L1–L4, la celda siguiente carga `PARTIDA` con tus funciones y lo guarda todo en `d`, un objeto `Datos` que reciben todas las funciones de los apartados siguientes. Debajo muestra un resumen de la partida.

    Antes de cargarla, `cargar` comprueba que lo que devuelven tus funciones es coherente (la función `comprobar_coherencia` del módulo `pong.analisis`). Si alguna comprobación falla, **no se carga la partida**: el resumen y todas las figuras muestran qué comprobación ha fallado, y tienes que corregir L1–L4. Comprueba que:

    - `meta` tiene las claves pedidas y `intercambios`, `ticks`, `juego` y `vuelos` tienen las columnas pedidas, con esos nombres y en ese orden;
    - no hay valores nulos en `juego`, todas sus filas son `playing` y sus ticks son consecutivos dentro de cada intercambio;
    - los intercambios de `juego` y de `vuelos` son los mismos y están en `intercambios`;
    - cada intercambio terminado en punto tiene `hits + 1` vuelos y su mayor `rally_hits` es `hits`; cada nulo (se declara en el mismo tick del golpe número 100) tiene `hits` vuelos y su mayor `rally_hits` es `hits − 1`;
    - los intercambios terminados en punto tienen ganador y los nulos no;
    - los receptores de vuelos consecutivos de un intercambio se alternan.

    Lo que contiene `d`:

    - **`d.meta`** y **`d.intercambios`:** lo que devuelve L1.
    - **`d.ticks`**, **`d.juego`** y **`d.vuelos`:** lo que devuelven L2, L3 y L4.
    - **`d.verdad`:** la «verdad» del motor, que los bots no ven: una fila por tick (la fila `t` es el tick `t`) con las columnas `tick`, `ball_vx`, `ball_vy`, `ball_ay` y `ball_speed`. Se usa en P4.
    - **`d.nombre(lado)`:** nombre del bot de un lado (`"left"` o `"right"`).
    - **`filas_vuelo(d, v)`:** las filas de `d.juego` de un vuelo `v` (una fila de `d.vuelos`, por ejemplo de `d.vuelos.itertuples()`). Por ejemplo, las ordenadas del vuelo son `d.juego["ball_y"].to_numpy()[filas_vuelo(d, v)]`.
    - **`figura_sin_datos(titulo)`:** devuélvela cuando una figura no tenga datos que dibujar en la partida (por ejemplo, en un abandono).
    """)
    return


@app.cell
def _():
    d = cargar(PARTIDA, leer_registro, leer_ticks, limpiar, vuelos)
    resumen(d)
    return (d,)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Análisis de la partida (1,6 puntos)

    Cuatro proposiciones sobre el movimiento de la bola que el motor cumple. Para cada una programarás las funciones que la comprueban con los datos de la partida y una figura que lo muestra. Cada proposición vale 0,4 puntos.

    Todo se calcula con las posiciones registradas en el CSV (`d.juego`, `d.vuelos` y `d.ticks`); `d.verdad`, la verdad del motor, solo se usa en P4 para medir el error de las estimaciones.

    Notación: las observaciones de un vuelo (ver la definición en L4) son $y_0, y_1, \dots, y_{N-1}$, la columna `ball_y` de sus $N$ filas en `d.juego`, y $n$ cuenta los ticks desde el golpe (o el saque) que inició el vuelo: $n = 0$ es la primera fila del vuelo, la del golpe, donde $y_0 = y^*$ (en el primer vuelo de un intercambio, la primera fila `playing` tras el saque, con la bola en el centro).

    Se usa la notación de las leyes del movimiento del enunciado: $v_{x,n}$ y $v_{y,n}$ son las componentes de la velocidad de la bola al final del tick $n$ y $a_{y,n}$ su efecto, en coordenadas plegadas; $v_{x,0}$, $v_{y,0}$ y $a_{y,0}$, sus valores al empezar el vuelo. En el código, `vx`, `v0` y `a` son $v_{x,0}$, $v_{y,0}$ y $a_{y,0}$, y `vy` y `ay` son $v_{y,n}$ y $a_{y,n}$.

    ### P1. Movimiento entre golpes (0,4 puntos)

    **Proposición.** Sea $Y_n$ la ordenada **desplegada** de la bola en un vuelo (la que tendría si no rebotase en las paredes). Entonces existen $v_{y,0}$ y $a_{y,0}$ tales que

    $$\Delta Y_n = Y_n - Y_{n-1} = v_{y,0} + n\,a_{y,0}, \qquad Y_n = y_0 + n\,v_{y,0} + a_{y,0}\,\frac{n(n+1)}{2}.$$

    Mientras la bola no toca una pared, $Y_n = y_n$. El efecto $a_{y,0}$ es $0$ o $\pm\kappa$, con $\kappa$ = `KAPPA` = 0,005 px/tick².

    #### `v0_y_a(y)`

    Estima $v_{y,0}$ y $a_{y,0}$ con las tres primeras observaciones `y[0]`, `y[1]` y `y[2]` de un vuelo: $\Delta y_1 = y_1 - y_0 = v_{y,0} + a_{y,0}$ y la segunda diferencia $(y_2 - y_1) - (y_1 - y_0)$ es $a_{y,0}$. Devuelve `(nan, nan)` si hay menos de tres observaciones.

    **Ejemplo:** `v0_y_a(np.array([300.0, 304.005, 308.015]))` devuelve `(4.0, 0.005)`, salvo redondeo (`0.0049999999999954525`).
    """)
    return


@app.function
def v0_y_a(y: np.ndarray) -> tuple[float, float]:
    """Estima ``(v0, a)`` con las tres primeras observaciones de un vuelo.

    Devuelve ``(nan, nan)`` si hay menos de tres observaciones.
    """
    raise NotImplementedError("Por hacer")


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    #### `ticks_validos(y0, v0, a, n_obs)`

    Devuelve un array booleano de longitud `n_obs` que vale `True` en los $n \ge 1$ anteriores al primer contacto con una pared según el modelo: $n$ es válido si $Y_m \in [R, H-R]$ para todo $m \le n$. El tick $n = 0$ nunca es válido.

    **Ejemplo:** `ticks_validos(580.0, 4.0, 0.005, 6)` devuelve `[False, True, True, True, False, False]`: el modelo da $Y_n$ = 580, 584,005, 588,015, 592,03, 596,05 y 600,075, y $H - R = 594$.
    """)
    return


@app.function
def ticks_validos(y0: float, v0: float, a: float, n_obs: int) -> np.ndarray:
    """Máscara booleana de longitud ``n_obs``: ``True`` en los ``n ≥ 1`` válidos.

    Un tick es válido si la ordenada desplegada del modelo,
    ``Y_m = y0 + m·v0 + a·m(m+1)/2``, está en [R, H − R] para todo ``m ≤ n``.
    """
    raise NotImplementedError("Por hacer")


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    #### `residuos_p1(d)`

    Para cada vuelo con tres o más ticks, estima $v_{y,0}$ y $a_{y,0}$ con `v0_y_a` y calcula los residuos $\Delta y_n - (v_{y,0} + n\,a_{y,0})$ en sus ticks válidos, con $\Delta y_n = y_n - y_{n-1}$. Devuelve un `DataFrame` con una fila por tick válido y las columnas:

    - **`vuelo`**, **`n`**;
    - **`dy`:** $\Delta y_n$ medida;
    - **`modelo`:** $v_{y,0} + n\,a_{y,0}$;
    - **`residuo`:** `dy − modelo`;
    - **`rebote_inicial`:** `True` en todas las filas de un vuelo cuyo residuo máximo en valor absoluto supera 1e-6. Son vuelos con un rebote en sus tres primeras observaciones: `v0_y_a` los estima mal y se resuelven en P2. Un vuelo así puede no marcarse si el modelo (erróneo) predice el contacto con la pared enseguida: entonces sus ticks válidos son muy pocos y sus residuos, nulos.

    **Ejemplo:** con la partida de ejemplo las primeras filas son:

    | vuelo | n | dy | modelo | residuo | rebote_inicial |
    | --- | --- | --- | --- | --- | --- |
    | 0 | 1 | 2.728986 | 2.728986 | 0.0 | False |
    | 0 | 2 | 2.728986 | 2.728986 | 0.0 | False |
    | 0 | 3 | 2.728986 | 2.728986 | 0.0 | False |
    | 0 | 4 | 2.728986 | 2.728986 | 0.0 | False |
    """)
    return


@app.function
def residuos_p1(d: Datos) -> pd.DataFrame:
    """Residuos de P1 en los ticks válidos de los vuelos con 3 o más ticks.

    Returns:
        Una fila por tick válido, con las columnas ``vuelo``, ``n``, ``dy``
        (Δy_n medida), ``modelo`` (v0 + n·a), ``residuo`` (``dy − modelo``) y
        ``rebote_inicial`` (``True`` en todas las filas de un vuelo cuyo
        residuo máximo en valor absoluto supera 1e-6). Un vuelo con un
        rebote en sus tres primeras observaciones puede no marcarse si el
        modelo (erróneo) predice el contacto con la pared enseguida: entonces
        sus ticks válidos son muy pocos y sus residuos, nulos.
    """
    raise NotImplementedError("Por hacer")


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    #### `figura_p1(d)`

    Figura con dos paneles, uno junto al otro:

    - **Izquierda:** $\Delta y_n$ medida y el modelo $v_{y,0} + n\,a_{y,0}$ frente a $n$ en un vuelo con rebotes: el más largo de los que tienen algún rebote y no tienen rebote inicial (según `comprobar_p2`, de P2), preferiblemente con efecto ($a_{y,0} \neq 0$). Marca los rebotes con líneas verticales discontinuas.
    - **Derecha:** el residuo $|\Delta y_n - (v_{y,0} + n\,a_{y,0})|$ frente a $n$ en todos los ticks válidos de los vuelos sin rebote inicial, con el eje vertical en escala logarítmica. Los residuos nulos no se pueden dibujar en escala logarítmica: dibújalos en 1e-16.

    **Tipo de gráfico:** izquierda, puntos (medida) y línea (modelo) con líneas verticales; derecha, diagrama de dispersión con escala logarítmica en el eje vertical.
    """)
    return


@app.function
def figura_p1(d: Datos) -> plt.Figure:
    """Figura P1 (dos paneles; ver el enunciado de P1)."""
    raise NotImplementedError("Por hacer")


@app.cell
def _(d):
    apartado("Figura P1", figura_p1, d)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### P2. Plegado (0,4 puntos)

    **Proposición.** La ordenada observada es $y = F(Y)$, donde $F$ es la onda triangular de periodo $2L$ que pliega el recorrido en $[R, H-R]$:

    $$F(Y) = \begin{cases} R + m & \text{si } m \le L\\ R + 2L - m & \text{si } m > L\end{cases}, \qquad m = (Y - R) \bmod 2L.$$

    #### `plegar(Y)`

    La función $F$ aplicada elemento a elemento a un array (vectorizada con NumPy, sin bucles).

    **Ejemplo:** `plegar(np.array([-100, 300, 700, 1300]))` devuelve `[112.0, 300.0, 488.0, 124.0]`.
    """)
    return


@app.function
def plegar(Y: np.ndarray) -> np.ndarray:
    """La onda triangular F de periodo 2L, aplicada elemento a elemento."""
    raise NotImplementedError("Por hacer")


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    #### `desplegar(y)`

    Devuelve `(Y, v0, a)`: la ordenada desplegada $Y$ de un vuelo (un array de su misma longitud) y sus $v_{y,0}$ y $a_{y,0}$. Si hay un rebote en las tres primeras observaciones, hay que reflejarlas antes de estimar $v_{y,0}$ y $a_{y,0}$: $Y = 2R - y$ en la pared de abajo ($y < H/2$) y $Y = 2(H - R) - y$ en la de arriba. De los desdobles posibles, en este orden,

    1. ninguno,
    2. reflejar la tercera observación,
    3. reflejar la segunda y la tercera,

    se elige el primero con el que $F(Y) = y$ en todo el vuelo (con tolerancia 1e-6). Si el vuelo tiene menos de tres observaciones o ningún desdoble lo cumple, devuelve un array de `nan` de la misma longitud y `v0` y `a` iguales a `nan`.

    **Ejemplo:** el vuelo 3 de la partida de ejemplo empieza junto a la pared de abajo y rebota enseguida: sus primeras observaciones son `[6.1233, 11.8926, 17.9085, 23.9243, …]`. `desplegar` las despliega en `[6.1233, 0.1074, -5.9085, -11.9243, …]`, con `v0` = −6.01586 y `a` ≈ 0 (−2,1e-14).
    """)
    return


@app.function
def desplegar(y: np.ndarray) -> tuple[np.ndarray, float, float]:
    """Ordenada desplegada ``Y`` de un vuelo y su ``(v0, a)``.

    Returns:
        ``(Y, v0, a)``; si el vuelo tiene menos de tres observaciones o
        ningún desdoble cumple F(Y) = y (con tolerancia 1e-6), ``Y`` es un
        array de ``nan`` de la misma longitud y ``v0`` y ``a`` son ``nan``.
    """
    raise NotImplementedError("Por hacer")


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    #### `ajuste_mc(Y)`

    Devuelve `(y0, v0, a)` ajustados por mínimos cuadrados (`np.linalg.lstsq`) al modelo $Y_n = y_0 + n\,v_{y,0} + a_{y,0}\,n(n+1)/2$ sobre la ordenada desplegada: la matriz del sistema tiene las columnas $1$, $n$ y $n(n+1)/2$.

    **Ejemplo:** con la `Y` del vuelo 3 del ejemplo anterior, `ajuste_mc(Y)` devuelve `(6.12327, -6.01586, -1.97e-14)`, aproximadamente.
    """)
    return


@app.function
def ajuste_mc(Y: np.ndarray) -> tuple[float, float, float]:
    """``(y0, v0, a)`` por mínimos cuadrados con el modelo de P1."""
    raise NotImplementedError("Por hacer")


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    #### `comprobar_p2(d)`

    Devuelve un `DataFrame` con una fila por cada vuelo con tres o más ticks que se puede desplegar (`desplegar` no da `nan`) y las columnas:

    - **`vuelo`**, **`n_ticks`**;
    - **`error_plegado`:** máximo de $|F(Y) - y|$ en el vuelo;
    - **`v0`**, **`a`:** los de `desplegar`;
    - **`y0_mc`**, **`v0_mc`**, **`a_mc`:** los de `ajuste_mc`;
    - **`rebotes`:** número de veces que $Y$ cruza una frontera $R + kL$ ($k$ entero), es decir, número de cambios de $\lfloor (Y - R)/L \rfloor$;
    - **`rebote_inicial`:** `True` si hubo que reflejar alguna de las tres primeras observaciones.

    **Ejemplo:** con la partida de ejemplo las primeras filas son (redondeadas):

    | vuelo | n_ticks | error_plegado | v0 | a | y0_mc | v0_mc | a_mc | rebotes | rebote_inicial |
    | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
    | 0 | 69 | 5.7e-14 | 2.728986 | 0.0 | 300.0 | 2.728986 | -3.5e-16 | 0 | False |
    | 1 | 129 | 4.5e-10 | -2.999471 | 5.7e-14 | 485.900080 | -2.999471 | 5.7e-14 | 0 | False |
    | 2 | 109 | 2.6e-11 | -0.585754 | -0.005 | 99.398888 | -0.585754 | -0.005 | 0 | False |
    | 3 | 173 | 3.1e-10 | -6.015860 | -2.1e-14 | 6.123266 | -6.015860 | -2.0e-14 | 2 | True |
    """)
    return


@app.function
def comprobar_p2(d: Datos) -> pd.DataFrame:
    """Una fila por vuelo con 3 o más ticks que se puede desplegar.

    Returns:
        Columnas ``vuelo``, ``n_ticks``, ``error_plegado`` (máximo de
        |F(Y) − y|), ``v0``, ``a`` (de ``desplegar``), ``y0_mc``, ``v0_mc``,
        ``a_mc`` (de ``ajuste_mc``), ``rebotes`` (número de veces que Y
        cruza una frontera R + kL) y ``rebote_inicial`` (``True`` si hubo que
        reflejar alguna de las tres primeras observaciones).
    """
    raise NotImplementedError("Por hacer")


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    #### `figura_p2(d)`

    Trayectoria de la bola en un vuelo con dos o más rebotes: el más largo de los que no tienen rebote inicial (si no hay ninguno, el más largo con algún rebote). Dibuja frente al tick la ordenada desplegada $Y$ y la plegada $y = F(Y)$, con líneas horizontales punteadas en las fronteras $R + kL$ que alcanza $Y$ y continuas en las paredes ($R$ y $H - R$).

    **Tipo de gráfico:** líneas, con líneas horizontales de referencia.
    """)
    return


@app.function
def figura_p2(d: Datos) -> plt.Figure:
    """Figura P2 (ver el enunciado de P2)."""
    raise NotImplementedError("Por hacer")


@app.cell
def _(d):
    apartado("Figura P2", figura_p2, d)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### P3. Cruce con la raqueta (0,4 puntos)

    **Proposición.** Sea $x_n = x_0 + n\,v_{x,0}$ la abscisa de la bola en un vuelo y $X$ el plano del centro de la bola en el impacto (`X_IZQ` o `X_DER`, según el receptor). El primer tick con cruce es $n^* = \lfloor (X - x_0)/v_{x,0} \rfloor + 1$, en los dos sentidos; la fracción del tick en la que cruza es $\tau = (X - x_{n^*-1})/v_{x,0}$; la ordenada de impacto es

    $$y^* = F\big(Y_{n^*-1} + \tau\,(Y_{n^*} - Y_{n^*-1})\big);$$

    y hay golpe si y solo si $|y^* - p| \le 46$ (`ALCANCE`), con $p$ la posición de la raqueta del receptor en el tick del cruce.

    #### `cruce(x0, vx, X)`

    Devuelve $(n^*, \tau)$.

    **Ejemplo:** el vuelo 0 de la partida de ejemplo sale del saque con $x_0 = 400$ y $v_{x,0} = 5{,}343467$ hacia la derecha. `cruce(400.0, 5.343467, X_DER)` devuelve `(69, 0.1205667)`, aproximadamente.
    """)
    return


@app.function
def cruce(x0: float, vx: float, X: float) -> tuple[int, float]:
    """``(n*, τ)``: primer tick con cruce del plano ``X`` y fracción del tick."""
    raise NotImplementedError("Por hacer")


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    #### `ordenada_impacto(y0, v0, a, n, tau)`

    Devuelve $y^*$ para el cruce en el tick $n$ con fracción $\tau$, con $Y_m$ dada por el modelo de P1.

    **Ejemplo:** en el vuelo 0 del ejemplo anterior $y_0 = 300$, $v_{y,0} = 2{,}728986$ y $a_{y,0} = 0$; `ordenada_impacto(300.0, 2.728986, 0.0, 69, 0.1205667)` devuelve 485,9001, aproximadamente, y la ordenada de impacto registrada (la `ball_y` del tick 129, primera fila del vuelo 1) es 485,90008.
    """)
    return


@app.function
def ordenada_impacto(y0: float, v0: float, a: float, n: int, tau: float) -> float:
    """``y*`` del cruce en el tick ``n`` con fracción ``tau`` (modelo de P1)."""
    raise NotImplementedError("Por hacer")


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    #### `comprobar_p3(d)`

    Devuelve un `DataFrame` con una fila por cada vuelo que termina en golpe o fallo y se puede desplegar, con las columnas:

    - **`vuelo`**, **`receptor`**, **`final`:** las de `d.vuelos`;
    - **`tick_cruce`:** `tick_ini` + $n^*$;
    - **`y_pred`:** $y^*$;
    - **`y_reg`:** la ordenada de impacto registrada, la `ball_y` de la primera fila del vuelo siguiente si hay golpe; `nan` si hay fallo;
    - **`p`:** la raqueta del receptor en la fila `tick_cruce` de `d.ticks` (`nan` si no existe);
    - **`golpe_pred`:** $|y^* - p| \le 46$;
    - **`s`:** la velocidad de intercambio, $s = \sqrt{v_{x,0}^2 + v_{y,0}^2}$, con $v_{x,0} = x_1 - x_0$.

    **Ejemplo:** con la partida de ejemplo las primeras filas son:

    | vuelo | receptor | final | tick_cruce | y_pred | y_reg | p | golpe_pred | s |
    | --- | --- | --- | --- | --- | --- | --- | --- | --- |
    | 0 | right | golpe | 129 | 485.900080 | 485.900080 | 500.0 | True | 6.0 |
    | 1 | left | golpe | 258 | 99.398888 | 99.398888 | 100.0 | True | 6.396554 |
    | 2 | right | golpe | 367 | 6.123266 | 6.123266 | 44.0 | True | 6.720770 |
    """)
    return


@app.function
def comprobar_p3(d: Datos) -> pd.DataFrame:
    """Predicción del cruce de cada vuelo que termina en golpe o fallo.

    Solo vuelos que se pueden desplegar (``desplegar`` no da ``nan``).

    Returns:
        Columnas ``vuelo``, ``receptor``, ``final``, ``tick_cruce``
        (``tick_ini + n*``), ``y_pred`` (y*), ``y_reg`` (``ball_y`` en la
        primera fila del vuelo siguiente si hay golpe; ``nan`` si hay fallo),
        ``p`` (raqueta del receptor en la fila ``tick_cruce`` de
        ``d.ticks``), ``golpe_pred`` (|y* − p| ≤ 46) y ``s`` (velocidad de
        intercambio, √(v_{x,0}² + v_{y,0}²)).
    """
    raise NotImplementedError("Por hacer")


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    #### `figura_p3(d)`

    Figura con dos paneles, uno junto al otro, con los vuelos que terminan en golpe:

    - **Izquierda:** $y^*$ predicha frente a la registrada, con la diagonal $y^* = y$ como referencia.
    - **Derecha:** histograma del error, $y^*$ predicha menos registrada (30 clases). Añade un texto con cuántos fallos cumplen $|y^* - p| > 46$, de cuántos.

    **Tipo de gráfico:** izquierda, diagrama de dispersión con una recta de referencia; derecha, histograma.
    """)
    return


@app.function
def figura_p3(d: Datos) -> plt.Figure:
    """Figura P3 (ver el enunciado de P3)."""
    raise NotImplementedError("Por hacer")


@app.cell
def _(d):
    apartado("Figura P3", figura_p3, d)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### P4. Velocidades plegadas y verdad del motor (0,4 puntos)

    **Proposición.** En coordenadas plegadas, al final del tick $n$ de un vuelo,

    $$v_{y,n} = (-1)^{k_n}\,(v_{y,0} + n\,a_{y,0}), \qquad a_{y,n} = (-1)^{k_n}\,a_{y,0},$$

    y $v_{x,n} = v_{x,0}$, donde $k_n = \lfloor (Y_n - R)/L \rfloor \bmod 2$ es la paridad del plegado.

    #### `velocidades(d)`

    Calcula $v_{x,n}$, $v_{y,n}$ y $a_{y,n}$ en cada tick de los vuelos que se pueden desplegar, con los resultados de P1 y P2. Devuelve un `DataFrame` con las columnas `tick`, `vuelo`, `n` (ticks desde el golpe), `vx`, `vy` y `ay`. Puedes compararlas con `d.verdad`.

    **Ejemplo:** con la partida de ejemplo las primeras filas son:

    | tick | vuelo | n | vx | vy | ay |
    | --- | --- | --- | --- | --- | --- |
    | 60 | 0 | 0 | 5.343467 | 2.728986 | 0.0 |
    | 61 | 0 | 1 | 5.343467 | 2.728986 | 0.0 |
    | 62 | 0 | 2 | 5.343467 | 2.728986 | 0.0 |
    """)
    return


@app.function
def velocidades(d: Datos) -> pd.DataFrame:
    """``vx``, ``vy`` y ``ay`` plegadas en cada tick de los vuelos desplegables.

    Returns:
        Columnas ``tick``, ``vuelo``, ``n`` (ticks desde el golpe), ``vx``,
        ``vy`` y ``ay``.
    """
    raise NotImplementedError("Por hacer")


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    #### `estimar_ultimas(y)`

    Lo que haría un bot en cada tick: estima $v_{y,n}$ y $a_{y,n}$, plegadas, en la **última** observación de `y` usando solo las últimas (como mucho tres). Devuelve `(vy, ay)`:

    - con una observación, `(nan, nan)`;
    - con dos, `vy` $= y_1 - y_0$ y `ay` $= 0$;
    - con tres o más, toma las tres últimas y prueba los desdobles de `desplegar`, en el mismo orden; elige el primero que da $a_{y,0} \in \{-\kappa, 0, \kappa\}$ (con tolerancia 1e-9) y devuelve su última diferencia y su $a$, con el signo $(-1)^{k}$ de la última observación. Si ninguno lo cumple, `(nan, nan)`.

    **Ejemplo:** `estimar_ultimas(np.array([300.0]))` devuelve `(nan, nan)`; `estimar_ultimas(np.array([300.0, 304.0]))`, `(4.0, 0.0)`; y `estimar_ultimas(np.array([300.0, 304.005, 308.015]))`, `(4.01, 0.005)`, salvo redondeo.
    """)
    return


@app.function
def estimar_ultimas(y: np.ndarray) -> tuple[float, float]:
    """``(vy, ay)`` plegadas en la última observación, con las últimas (≤ 3).

    Con una sola observación devuelve ``(nan, nan)``.
    """
    raise NotImplementedError("Por hacer")


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    #### `error_estimacion(d)`

    Para cada vuelo y cada $n \ge 1$, aplica `estimar_ultimas` a las observaciones $y_0, \dots, y_n$ y compara el resultado con `ball_vy` y `ball_ay` de `d.verdad` en ese tick. Devuelve un `DataFrame` con las columnas `tick`, `n`, `error_vy` y `error_ay` (errores en valor absoluto).

    **Ejemplo:** con la partida de ejemplo las primeras filas son:

    | tick | n | error_vy | error_ay |
    | --- | --- | --- | --- |
    | 61 | 1 | 1.8e-15 | 0.0 |
    | 62 | 2 | 1.8e-15 | 0.0 |
    | 63 | 3 | 1.8e-15 | 0.0 |
    """)
    return


@app.function
def error_estimacion(d: Datos) -> pd.DataFrame:
    """Error de ``estimar_ultimas`` frente a ``d.verdad`` en cada tick.

    Returns:
        Columnas ``tick``, ``n`` (ticks desde el golpe, n ≥ 1), ``error_vy``
        y ``error_ay`` (valores absolutos).
    """
    raise NotImplementedError("Por hacer")


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    #### `figura_p4(d)`

    Error máximo de la estimación de $v_{y,n}$ y de $a_{y,n}$ (sobre todos los vuelos) frente a los ticks desde el golpe, $n = 1, \dots, 30$, con el eje vertical en escala logarítmica. Dibuja los errores nulos en 1e-16.

    **Tipo de gráfico:** puntos unidos por líneas (una serie para $v_{y,n}$ y otra para $a_{y,n}$), con escala logarítmica en el eje vertical.
    """)
    return


@app.function
def figura_p4(d: Datos) -> plt.Figure:
    """Figura P4 (ver el enunciado de P4)."""
    raise NotImplementedError("Por hacer")


@app.cell
def _(d):
    apartado("Figura P4", figura_p4, d)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Análisis estadístico (1,0 puntos de base y 1,5 de ampliación)

    Ocho figuras sobre el juego de los dos bots. S1, S2, S5 y S7 son de la **base** (0,25 puntos cada una); S3 (0,5), S6 (0,4), S4 (0,3) y S8 (0,3) son de **ampliación**.

    ### Intervalos de confianza para una proporción

    Si un bot ha fallado $k$ de las $n$ bolas que le han llegado a cierta velocidad, la proporción observada $\hat p = k/n$ es solo una **estimación** de la probabilidad $p$ de fallar a esa velocidad, que no conocemos: con otra partida saldría otro valor. Para expresar esa incertidumbre se da, junto a $\hat p$, un **intervalo de confianza**.

    Un intervalo de confianza del 95 % para $p$ es un intervalo $[p_-, p_+]$ calculado a partir de los datos mediante un procedimiento que, si se repitiese el experimento muchas veces, daría intervalos que contienen el verdadero $p$ en el 95 % de las repeticiones. No dice que $p$ esté en el intervalo con probabilidad 0,95 (en una partida concreta, lo está o no lo está), sino que el procedimiento acierta el 95 % de las veces. Cuantos más datos, más estrecho es el intervalo: con $n$ pequeño la incertidumbre es grande.

    El intervalo más conocido, el de **Wald**, se basa en la aproximación normal de $\hat p$:

    $$\hat p \pm z\sqrt{\frac{\hat p(1-\hat p)}{n}},$$

    donde $z = 1{,}96$ es el valor que deja una probabilidad de 0,025 a su derecha en la distribución normal estándar (el 95 % central queda entre $-1{,}96$ y $1{,}96$). Funciona mal cuando $n$ es pequeño o $\hat p$ está cerca de 0 o de 1, que es lo habitual aquí: con $k = 0$ da el intervalo $[0, 0]$, como si fuese seguro que el bot nunca falla, y en otros casos se sale de $[0, 1]$.

    El **intervalo de Wilson**, que es el que usarás, corrige esos defectos. Sus extremos son

    $$\frac{\hat p + \dfrac{z^2}{2n} \pm z\sqrt{\dfrac{\hat p(1-\hat p)}{n} + \dfrac{z^2}{4n^2}}}{1 + \dfrac{z^2}{n}},$$

    con $z = 1{,}96$ para el 95 %. Su centro no es $\hat p$, sino un valor desplazado hacia 1/2, y queda siempre dentro de $[0, 1]$.

    #### `intervalo_wilson(k, n, z=1.96)`

    Devuelve `(inferior, superior)`, los extremos del intervalo de Wilson para `k` éxitos en `n` ensayos. Debe funcionar con números y con arrays de NumPy o columnas de pandas (vectorizada, sin bucles). Con `n = 0` los extremos son `nan`. Asegúrate de que inferior ≤ $\hat p$ ≤ superior y de que ambos están en $[0, 1]$ (por ejemplo, con `np.clip`): con $k = 0$ o $k = n$ el redondeo puede dejarlos fuera por unos 1e-18, y Matplotlib rechaza barras de error negativas.

    **Ejemplos:**

    - `intervalo_wilson(16, 27)` devuelve `(0.4073, 0.7549)`, aproximadamente: el que saca ganó 16 de los 27 puntos de la partida de ejemplo ($\hat p = 0{,}593$), pero los datos son compatibles con que no haya ventaja ($p = 0{,}5$).
    - `intervalo_wilson(0, 365)` devuelve `(0.0, 0.0104)`: aunque no haya ningún fallo en 365 vuelos lentos, el intervalo admite hasta un 1 % de fallos (Wald daría $[0, 0]$).
    - `intervalo_wilson(8, 117)` devuelve `(0.0351, 0.1291)`.
    """)
    return


@app.function
def intervalo_wilson(
    k: np.ndarray, n: np.ndarray, z: float = 1.96
) -> tuple[np.ndarray, np.ndarray]:
    """Intervalo de Wilson: ``(inferior, superior)`` para ``k`` éxitos en ``n``.

    Funciona con números o con arrays. Asegura inferior ≤ k/n ≤ superior y
    que ambos estén en [0, 1]: con k = 0 o k = n el redondeo puede dejarlos
    fuera por unos 1e-18, y Matplotlib rechaza barras de error negativas.
    """
    raise NotImplementedError("Por hacer")


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### Los golpes

    #### `golpes(d)`

    Devuelve un `DataFrame` con una fila por golpe entre dos vuelos desplegables del mismo intercambio (los usan S2 y S3), con las columnas:

    - **`tick`:** el de la primera fila del vuelo nuevo;
    - **`golpeador`:** `"left"` o `"right"`, el receptor del vuelo que termina;
    - **`u`:** punto de impacto en la raqueta, $u = (y^* - p)/46$, con $y^*$ la `ball_y` de esa fila y $p$ la raqueta del golpeador en ella: $-1$ es el borde superior, $0$ el centro y $1$ el borde inferior;
    - **`c`:** comando del golpeador en el tick anterior: $-1$ `UP`, $0$ `STAY` y $1$ `DOWN`;
    - **`s_antes`**, **`s_despues`:** la velocidad de intercambio $s = \sqrt{v_{x,0}^2 + v_{y,0}^2}$ de los dos vuelos.

    **Ejemplo:** con la partida de ejemplo las primeras filas son:

    | tick | golpeador | u | c | s_antes | s_despues |
    | --- | --- | --- | --- | --- | --- |
    | 129 | right | -0.306520 | 0 | 6.0 | 6.396554 |
    | 258 | left | -0.013068 | -1 | 6.396554 | 6.720770 |
    | 367 | right | -0.823407 | 0 | 6.720770 | 7.347340 |
    """)
    return


@app.function
def golpes(d: Datos) -> pd.DataFrame:
    """Una fila por golpe entre dos vuelos desplegables del mismo intercambio.

    Returns:
        Columnas ``tick`` (primera fila del vuelo nuevo), ``golpeador``
        (``"left"`` o ``"right"``), ``u`` ((y* − p)/46, con y* la
        ``ball_y`` y p la raqueta del golpeador en esa fila), ``c`` (comando
        del golpeador en el tick anterior: −1 UP, 0 STAY, 1 DOWN),
        ``s_antes`` y ``s_despues`` (√(v_{x,0}² + v_{y,0}²) de los dos vuelos).
    """
    raise NotImplementedError("Por hacer")


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### S1. Golpes por intercambio (base, 0,25 puntos)

    #### `figura_s1(d)`

    Distribución del número de golpes (`hits`) de los intercambios que terminan en punto, según quién ganó el punto: una caja por bot ganador, con su nombre y el número de puntos que ganó en la etiqueta.

    **Tipo de gráfico:** diagrama de cajas.
    """)
    return


@app.function
def figura_s1(d: Datos) -> plt.Figure:
    """S1 (base). Golpes por intercambio según quién ganó el punto.

    Diagrama de cajas, una caja por bot ganador (solo intercambios que
    terminan en punto).
    """
    raise NotImplementedError("Por hacer")


@app.cell
def _(d):
    apartado("Figura S1", figura_s1, d)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### S2. Punto de impacto (base, 0,25 puntos)

    #### `figura_s2(d)`

    Distribución del punto de impacto $u$ (de `golpes`) de cada bot: un panel por bot, uno junto al otro, con las mismas 20 clases de igual anchura en $[-1, 1]$ y los mismos ejes. El título de cada panel da el nombre del bot y la media y la desviación típica de su $u$.

    **Tipo de gráfico:** histogramas, uno por panel.
    """)
    return


@app.function
def figura_s2(d: Datos) -> plt.Figure:
    """S2 (base). Punto de impacto u de cada bot.

    Histogramas, un panel por bot, con los mismos intervalos en [−1, 1]
    (20 clases); el título de cada panel da la media y la desviación típica.
    """
    raise NotImplementedError("Por hacer")


@app.cell
def _(d):
    apartado("Figura S2", figura_s2, d)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### S3. Ley de aceleración (ampliación, 0,5 puntos)

    Según las reglas, en cada golpe la velocidad de intercambio $s$ se multiplica por $1{,}05\,(1 + 0{,}05\,|u|)$: la razón $s_\text{después}/s_\text{antes}$ es una función lineal de $|u|$ con ordenada en el origen 1,05 y pendiente 0,0525. Compruébalo con los datos por regresión lineal.

    #### `figura_s3(d)`

    Figura con dos paneles, uno junto al otro:

    - **Izquierda:** la razón $s_\text{después}/s_\text{antes}$ de cada golpe frente a $|u|$, con la recta ajustada por mínimos cuadrados (`np.polyfit` de grado 1), con su ecuación en la leyenda, y la recta teórica $1{,}05\,(1 + 0{,}05\,|u|)$, discontinua.
    - **Derecha:** los residuos del ajuste frente a $|u|$.

    **Tipo de gráfico:** izquierda, diagrama de dispersión con dos rectas; derecha, diagrama de dispersión.
    """)
    return


@app.function
def figura_s3(d: Datos) -> plt.Figure:
    """S3 (ampliación). Ley de aceleración por regresión lineal.

    Dispersión de s_después/s_antes frente a |u| con la recta ajustada por
    mínimos cuadrados (``np.polyfit``) y la teórica 1,05·(1 + 0,05·|u|), y un
    segundo panel con los residuos del ajuste.
    """
    raise NotImplementedError("Por hacer")


@app.cell
def _(d):
    apartado("Figura S3", figura_s3, d)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### S4. Ordenada de llegada (ampliación, 0,3 puntos)

    #### `figura_s4(d)`

    Distribución de la ordenada de llegada $y^*$ predicha (de `comprobar_p3`) de los vuelos que recibe cada bot, separando golpes y fallos: un panel por bot receptor, uno junto al otro, con 20 clases de igual anchura en $[R, H - R]$, los golpes y los fallos apilados en cada clase y una leyenda.

    **Tipo de gráfico:** histogramas apilados, uno por panel.
    """)
    return


@app.function
def figura_s4(d: Datos) -> plt.Figure:
    """S4 (ampliación). Ordenada de llegada y* de golpes y fallos, por bot.

    Histograma apilado (golpes y fallos), un panel por bot receptor, con
    20 clases en [R, H − R].
    """
    raise NotImplementedError("Por hacer")


@app.cell
def _(d):
    apartado("Figura S4", figura_s4, d)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### S5. Fallos según la velocidad (base, 0,25 puntos)

    #### `tasa_fallos(d, clases=6)`

    Agrupa los vuelos de `comprobar_p3` (golpes y fallos de los dos bots) en `clases` intervalos de igual anchura de la velocidad `s`, con `pd.cut`. Devuelve un `DataFrame` con una fila por clase con al menos un vuelo y las columnas:

    - **`clase`:** el intervalo;
    - **`centro`:** su punto medio;
    - **`n`:** número de vuelos;
    - **`fallos`:** número de fallos;
    - **`p`:** `fallos / n`;
    - **`inferior`**, **`superior`:** el intervalo de Wilson del 95 %.

    **Ejemplo:** con la partida de ejemplo devuelve (redondeado):

    | clase | centro | n | fallos | p | inferior | superior |
    | --- | --- | --- | --- | --- | --- | --- |
    | (5.951, 14.176] | 10.064 | 365 | 0 | 0.0 | 0.0 | 0.0104 |
    | (14.176, 22.351] | 18.264 | 188 | 0 | 0.0 | 0.0 | 0.0200 |
    | (22.351, 30.527] | 26.439 | 117 | 8 | 0.0684 | 0.0351 | 0.1291 |
    | (30.527, 38.703] | 34.615 | 38 | 16 | 0.4211 | 0.2785 | 0.5781 |
    | (38.703, 46.879] | 42.791 | 6 | 2 | 0.3333 | 0.0968 | 0.7000 |
    | (46.879, 55.054] | 50.967 | 2 | 1 | 0.5 | 0.0945 | 0.9055 |
    """)
    return


@app.function
def tasa_fallos(d: Datos, clases: int = 6) -> pd.DataFrame:
    """Proporción de fallos según la velocidad de intercambio (para S5).

    Agrupa con ``pd.cut`` en ``clases`` intervalos de igual anchura de ``s``
    los vuelos de ``comprobar_p3`` (golpes y fallos de los dos bots).

    Returns:
        Una fila por clase con al menos un vuelo: ``clase`` (el intervalo),
        ``centro``, ``n``, ``fallos``, ``p`` (fallos / n), ``inferior`` y
        ``superior`` (intervalo de Wilson).
    """
    raise NotImplementedError("Por hacer")


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    #### `figura_s5(d)`

    Proporción de fallos de cada clase de velocidad de `tasa_fallos`, con su intervalo de Wilson del 95 % como barra de error y el número de vuelos $n$ de la clase escrito sobre cada barra.

    **Tipo de gráfico:** diagrama de barras con barras de error.
    """)
    return


@app.function
def figura_s5(d: Datos) -> plt.Figure:
    """S5 (base). Proporción de fallos según la velocidad (barras con IC)."""
    raise NotImplementedError("Por hacer")


@app.cell
def _(d):
    apartado("Figura S5", figura_s5, d)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### S6. Ventaja del saque (ampliación, 0,4 puntos)

    #### `ventaja_saque(d)`

    Proporción de los puntos (intercambios terminados en punto) que gana el que saca. El que saca un intercambio es el valor de la columna `server` en sus filas. Devuelve un `DataFrame` con una fila `"total"` y una por bot que saca (con su nombre, primero el de la izquierda), y las columnas `quien`, `n` (puntos sacados), `ganados`, `p` (`ganados / n`, `nan` si `n` = 0), `inferior` y `superior` (intervalo de Wilson del 95 %).

    **Ejemplo:** con la partida de ejemplo devuelve (redondeado):

    | quien | n | ganados | p | inferior | superior |
    | --- | --- | --- | --- | --- | --- |
    | total | 27 | 16 | 0.5926 | 0.4073 | 0.7549 |
    | hard | 21 | 16 | 0.7619 | 0.5491 | 0.8937 |
    | medium | 6 | 0 | 0.0 | 0.0 | 0.3903 |
    """)
    return


@app.function
def ventaja_saque(d: Datos) -> pd.DataFrame:
    """Proporción de puntos que gana el que saca (para S6).

    El que saca un intercambio es la columna ``server`` de sus filas.

    Returns:
        Filas ``"total"`` y una por bot que saca (con su nombre), con las
        columnas ``quien``, ``n`` (puntos sacados), ``ganados``, ``p``,
        ``inferior`` y ``superior`` (intervalo de Wilson).
    """
    raise NotImplementedError("Por hacer")


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    #### `figura_s6(d)`

    Una barra por fila de `ventaja_saque` con al menos un punto sacado, con su intervalo de Wilson del 95 % como barra de error, una línea horizontal discontinua en 0,5 (sin ventaja) y, en la etiqueta de cada barra, quién saca y `ganados/n`. Eje vertical entre 0 y 1.

    **Tipo de gráfico:** diagrama de barras con barras de error y una línea horizontal de referencia.
    """)
    return


@app.function
def figura_s6(d: Datos) -> plt.Figure:
    """S6 (ampliación). Ventaja del saque: barras con IC y referencia en 0,5."""
    raise NotImplementedError("Por hacer")


@app.cell
def _(d):
    apartado("Figura S6", figura_s6, d)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### S7. Comportamiento de cada bot (base, 0,25 puntos)

    #### `recorrido(d)`

    Distancia que recorre cada raqueta en cada vuelo: la suma de $|\Delta p|$ entre filas consecutivas del vuelo. Devuelve un `DataFrame` con las columnas `vuelo`, `bot` (nombre) y `distancia` (px): primero todos los vuelos del bot de la izquierda y luego los del de la derecha.

    **Ejemplo:** con la partida de ejemplo las primeras filas son:

    | vuelo | bot | distancia |
    | --- | --- | --- |
    | 0 | hard | 0.0 |
    | 1 | hard | 192.0 |
    | 2 | hard | 200.0 |
    | 3 | hard | 208.0 |
    """)
    return


@app.function
def recorrido(d: Datos) -> pd.DataFrame:
    """Distancia que recorre cada raqueta en cada vuelo (para S7).

    Returns:
        Columnas ``vuelo``, ``bot`` (nombre) y ``distancia`` (suma de
        |Δp| entre filas consecutivas del vuelo, en px).
    """
    raise NotImplementedError("Por hacer")


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    #### `figura_s7(d)`

    Figura con dos paneles, uno junto al otro:

    - **Izquierda:** frecuencia relativa de cada comando (`UP`, `STAY` y `DOWN`) de cada bot en las filas de `d.juego`, con las barras de los dos bots agrupadas por comando y una leyenda.
    - **Derecha:** distribución de la distancia recorrida por la raqueta de cada bot en cada vuelo (de `recorrido`), con la mediana marcada.

    **Tipo de gráfico:** izquierda, diagrama de barras agrupadas; derecha, diagrama de violín.
    """)
    return


@app.function
def figura_s7(d: Datos) -> plt.Figure:
    """S7 (base). Comportamiento de cada bot.

    Izquierda: barras agrupadas con la frecuencia relativa de UP, STAY y DOWN
    de cada bot (filas ``playing``). Derecha: diagrama de violín de la
    distancia que recorre cada raqueta en cada vuelo.
    """
    raise NotImplementedError("Por hacer")


@app.cell
def _(d):
    apartado("Figura S7", figura_s7, d)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### S8. Evolución del marcador (ampliación, 0,3 puntos)

    #### `marcador(d)`

    Una fila por punto (intercambio terminado en punto) con las columnas:

    - **`tick`:** el `end_tick` del intercambio;
    - **`diferencia`:** puntos acumulados en toda la partida por el bot de la izquierda menos los del de la derecha;
    - **`fin_set`:** `True` si ese punto cierra un set, según `pe.set_won` aplicado al marcador del set (que vuelve a 0–0 al empezar el siguiente).

    **Ejemplo:** con la partida de ejemplo las primeras filas son:

    | tick | diferencia | fin_set |
    | --- | --- | --- |
    | 1936 | 1 | False |
    | 3842 | 2 | False |
    | 5721 | 3 | False |

    y los dos sets terminan en los ticks 23 130 (diferencia 10) y 52 074 (diferencia 17).
    """)
    return


@app.function
def marcador(d: Datos) -> pd.DataFrame:
    """Evolución del marcador (para S8): una fila por punto.

    Returns:
        Columnas ``tick`` (``end_tick`` del intercambio), ``diferencia``
        (puntos acumulados de la izquierda menos de la derecha en toda la
        partida) y ``fin_set`` (``True`` si ese punto cierra un set, según
        ``pe.set_won`` aplicado al marcador del set).
    """
    raise NotImplementedError("Por hacer")


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    #### `figura_s8(d)`

    La diferencia de puntos frente al tick, desde 0 en el tick 0, con líneas verticales discontinuas en los finales de set y una línea horizontal en 0. En el título, los nombres de los bots.

    **Tipo de gráfico:** línea escalonada, con líneas de referencia.
    """)
    return


@app.function
def figura_s8(d: Datos) -> plt.Figure:
    """S8 (ampliación). Diferencia de puntos frente al tick.

    Líneas escalonadas, con líneas verticales en los finales de set.
    """
    raise NotImplementedError("Por hacer")


@app.cell
def _(d):
    apartado("Figura S8", figura_s8, d)
    return


if __name__ == "__main__":
    app.run()
