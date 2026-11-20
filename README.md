# Práctica Pong — Programación (23200), UIB

Programa un bot que juegue al Pong mejor que los tres bots de referencia
(Fácil, Medio y Difícil) y analiza sus partidas. Se evalúan tres ficheros de tu
repositorio:

- tu bot, la clase `Bot` de [`src/pong/bot.py`](src/pong/bot.py);
- tus tests, [`tests/test_bot.py`](tests/test_bot.py);
- tu notebook de análisis, [`notebook/analisis_mo.py`](notebook/analisis_mo.py).

El [enunciado de la práctica](https://uib-23200-programacion.github.io/website/es/practica/practica.html), con las reglas del juego, la
forma de entrega, la fecha límite y la evaluación, está en la web de la
asignatura. Los términos y símbolos (vuelo, ordenada plegada, efecto
$a_{y,n}$…) están definidos en [Definiciones y notación](https://uib-23200-programacion.github.io/website/es/practica/definiciones.html).
Este README explica cómo usar las herramientas del repositorio.

## 1. Crea tu copia (privada)

1. Pulsa **Use this template → Create a new repository**.
2. Elige **Private**. **Es obligatorio**: en un repositorio público tus
   compañeros verían tu bot antes de la evaluación. Una copia pública incumple
   las normas de entrega.

## 2. Abre el entorno de trabajo

Hay dos entornos soportados, con la misma configuración:

- **GitHub Codespaces (recomendado):** botón **Code → Codespaces → Create
  codespace on main**. No hay que instalar nada.
- **En tu ordenador, con Docker:** instala Docker Desktop, VS Code y la
  extensión *Dev Containers*. Clona tu repositorio y elige **Reopen in
  Container**. Funciona en PC (x86-64) y en Mac con Apple Silicon (ARM64).
  - **Windows:** clona el repositorio **dentro de WSL2** (por ejemplo, en
    `~/practica`), nunca en `C:\`, o todo irá muy lento.

La instalación directa de Python, sin Docker, **no está soportada**: los bots
Medio y Difícil van compilados para los entornos anteriores y no funcionarían.

Al abrirse el entorno se ejecuta `uv sync`, que instala Python 3.13 y todas
las bibliotecas.

## 3. Órdenes básicas

| Qué | Orden |
| --- | --- |
| Ejecutar los tests | `uv run pytest` |
| Comprobar los tipos de tu bot, como en la evaluación de la calidad | `uv run mypy src/pong/bot.py` |
| Jugar una partida contra Fácil y guardar su registro JSON | `uv run python -m pong.runner --rival easy` |
| Lo mismo, guardando también el CSV | `uv run python -m pong.runner --rival easy --csv` |
| Jugar contra tu propio bot | `uv run python -m pong.runner --rival mi_bot` |
| Medir tu nota de rendimiento contra Difícil | `uv run python -m pong.evaluate --rival hard --partidas 100` |
| Lo mismo, guardando cada partida y un resumen ordenado | `uv run python -m pong.evaluate --rival hard --partidas 100 --guardar` |
| Obtener el CSV de una partida guardada | `uv run python -m pong.registro partidas/partida_<semilla>.json` |
| Abrir el notebook de análisis | `uv run marimo edit --no-token notebook/analisis_mo.py` |

Los registros se guardan en `partidas/`:

- `runner` escribe `partidas/partida_<semilla>.json` (y el CSV con `--csv`).
- `evaluate --guardar` crea una carpeta por ejecución, por ejemplo
  `partidas/evaluate_hard_2026-11-03_1015/`, con el JSON de cada partida y
  `resumen.csv`: una fila por partida, **de la peor a la mejor**. Al terminar,
  `evaluate` te muestra tus cinco peores partidas: ábrelas en `pong.html` para
  ver qué falla.

El JSON contiene la partida completa: con su semilla y sus comandos, el motor
la reproduce exactamente. Ocupa poco (unos 5–12 KB en el repositorio), así que
**los JSON y los `resumen.csv` se suben a GitHub**: haz de vez en cuando
`git add partidas` y commit, o los perderás si borras el Codespace (GitHub
borra los Codespaces que llevan tiempo sin usarse). Los CSV de partida no se
suben (están en `.gitignore`): ocupan varios MB cada uno y se obtienen en
cualquier momento a partir del JSON con `pong.registro`, idénticos a los que
se habrían escrito al jugar.

El CSV tiene una fila por tick con **lo mismo que ven los bots**: `tick`,
`state`, posición de la bola (`ball_x`, `ball_y`), de las raquetas (`p_left`,
`p_right`), comandos (`cmd_left`, `cmd_right`), quién saca (`server`) y golpes
del intercambio (`rally_hits`). Las velocidades y el efecto de la bola no
están: tienes que estimarlos, como tu bot. Para comprobar tus estimaciones,
la «verdad» del motor se obtiene aparte: en cada tick, la velocidad
$(v_{x,n}, v_{y,n})$ (`ball_vx`, `ball_vy`), el efecto $a_{y,n}$ (`ball_ay`) y
la velocidad de intercambio $s$ (`ball_speed`):

```bash
uv run python -m pong.registro partidas/partida_<semilla>.json --verdad   # escribe también partida_<semilla>_verdad.csv
```

o en Python, `pong.registro.verdad(ruta)`, que devuelve una lista de
diccionarios (`pd.DataFrame(verdad(ruta))`).

`evaluate` juega como la evaluación oficial: alterna lados, cuenta el
porcentaje de **puntos** ganados y estima tu nota con las cotas de la rúbrica:
el rendimiento vale hasta 1 punto contra Fácil, 1 contra Medio y 1,5 contra
Difícil, sobre los 10 de la práctica.
La evaluación oficial usa semillas secretas, así que tu resultado solo variará
por azar. Con 100 partidas, ese margen ronda los dos puntos porcentuales.

**Opciones de `evaluate` y `runner`.** Sin `--partidas`, `evaluate` juega 20
partidas (10 en cada lado): sirve para probar rápido, pero el margen por azar
sube a unos 4–5 puntos porcentuales, así que para compararte con la evaluación
oficial usa `--partidas 100`. Con `--semilla-base S` fijas la primera semilla
(por defecto es aleatoria; en las semillas pares tu bot juega a la izquierda) y
con `--salida` cambias la carpeta `partidas/`. `evaluate` solo juega contra
Fácil, Medio y Difícil; para jugar contra tu propio bot usa
`runner --rival mi_bot`. `runner` juega una sola partida y, con `--semilla S` y
`--lado izquierda` o `--lado derecha`, repite exactamente una partida concreta.

**Comparar dos versiones de tu bot.** Para saber si un cambio en `bot.py`
mejora tu bot, ejecuta `evaluate` antes y después del cambio con la misma
semilla base, por ejemplo `--rival hard --partidas 100 --semilla-base 1000`, y
compara los dos porcentajes de puntos. Así las dos versiones empiezan las
mismas partidas (mismo saque inicial y misma dirección) y la diferencia se
debe sobre todo al cambio, no a la suerte de las semillas. No desaparece del
todo: en cuanto tu bot juega distinto, la partida sigue otro camino.

En VS Code también tienes, en *Ejecutar y depurar*, configuraciones para jugar
una partida o evaluar tu bot con puntos de ruptura en `bot.py`.

### Ver las partidas: `pong.html`

```bash
uv run python -m http.server 8000
```

VS Code avisa de que el puerto 8000 está disponible: ábrelo en el navegador y
añade `/pong.html` a la dirección. La página ejecuta el motor en el navegador
(con Pyodide, que se descarga de internet la primera vez) y tiene dos modos:

- **En directo:** tu bot contra Easy, contra sí mismo o contra una versión
  anterior guardada en `mis_bots/`, con pausa, avance tick a tick y salto al
  próximo golpe o punto. Tras editar `bot.py`, pulsa «Recargar bots».
- **Reproducción:** elige un registro JSON de `partidas/` (de `runner` o de
  `evaluate --guardar`) y la página reproduce la partida con el motor y
  comprueba que coincide con el registro. Así ves tus partidas contra Medium y
  Hard.

Los paneles muestran el `state` que recibe cada bot, los valores reales del
motor (la velocidad $(v_{x,n}, v_{y,n})$ y el efecto $a_{y,n}$, que tu bot
tiene que estimar), los `print` y las
excepciones de tu bot. Si tu bot guarda en `self.depuracion` un diccionario con
`objetivo_y`, `trayectoria` (lista de puntos (x, y)), `puntos` o `texto`, en
las coordenadas de su `state`, la página lo dibuja sobre el campo. Es opcional
y no afecta al juego.

### El notebook de análisis: `notebook/analisis_mo.py`

Es uno de tus entregables: un notebook de [Marimo](https://marimo.io) que
analiza **una partida cualquiera** a partir de su registro JSON. Ábrelo con

```bash
uv run marimo edit --no-token notebook/analisis_mo.py
```

y abre en el navegador la dirección que aparece (VS Code reenvía el puerto
2718). Con `--no-token` Marimo no pide contraseña; no hace falta, porque el
puerto solo es accesible para ti: no lo hagas público en la pestaña
*Puertos*. Al abrirlo, el notebook se ejecuta entero.

También puedes trabajar con él dentro de VS Code, con la extensión de marimo,
que ya viene instalada: abre el fichero, ejecuta la orden «marimo: Open as
marimo notebook» y, si te pregunta qué entorno usar, elige el intérprete de
`.venv` (no el modo *sandbox*). Si las celdas no se han ejecutado, pulsa
«Run all».

El notebook ya tiene el enunciado de cada apartado (con un ejemplo y el tipo
de gráfico de cada figura) y las funciones que debes escribir, con su nombre,
sus parámetros y su docstring; cada una empieza con `raise
NotImplementedError`. No cambies esos nombres ni parámetros: el profesor
corrige las funciones con tests propios. La clase `Datos`, que reciben las
funciones de las figuras, y las funciones de apoyo `filas_vuelo` y
`figura_sin_datos` están en `src/pong/analisis.py`; el notebook las importa y
no tienes que modificarlas.

- La partida que se analiza es la variable `PARTIDA` de la primera celda del
  notebook. Por defecto es `notebook/ejemplo.json` (Hard contra Medium);
  cámbiala por la ruta de cualquier partida tuya, absoluta o relativa a la
  raíz del repositorio, por ejemplo `PARTIDA = Path("partidas/partida_7.json")`.
- Las funciones de lectura y limpieza (L1–L4) son obligatorias y lo primero
  que debes hacer: una celda que va después de ellas carga la partida con
  ellas, y sin ellas no se dibuja ninguna figura. Antes de cargarla se
  comprueba que lo que devuelven es coherente; si no lo es, no se carga y el
  notebook dice qué comprobación ha fallado.
  **Son un requisito: si con la partida del profesor o con alguna de las de
  sus tests (normales, con nulo, con abandono o cortadas por tiempo) alguna
  de L1–L4 falla o no se puede cargar la partida, el notebook se califica
  con 0.** Compruébalo con `uv run pytest tests/test_notebook.py`, que carga
  con tus funciones `notebook/ejemplo.json` y las partidas raras de
  `notebook/raras/`. Con la partida cargada, mientras
  una función de los apartados siguientes esté por hacer o falle, su figura
  lo indica y el resto del notebook sigue funcionando.
- `notebook/ejemplo.html` es el enunciado del notebook con las figuras de la
  solución dibujadas con la partida de ejemplo, sin código: compara tus
  figuras con ellas. Para verlo en el Codespace, ejecuta
  `uv run python -m http.server 8000`, abre el puerto 8000 en el navegador y
  entra en `notebook/ejemplo.html` (o descárgalo con clic derecho →
  *Download* y ábrelo en tu ordenador).
- El profesor lo ejecutará sin interfaz, con esta orden, sobre una partida
  que no has visto (`--registro` sustituye a `PARTIDA`). Pruébala tú también
  con otras partidas:

  ```bash
  uv run marimo export html notebook/analisis_mo.py -o analisis.html -- --registro partidas/partida_<semilla>.json
  ```

`uv run pytest` incluye unos tests de forma del notebook
(`tests/test_notebook.py`): comprueban que las funciones conservan su firma y
que el notebook se ejecuta entero, no que sean correctas.

## 4. Normas

- **No modifiques `src/pong/pong_engine.py`.** Un test comprueba que no ha
  cambiado. La evaluación usa siempre el motor original.
- **Tu bot debe ser tuyo.** Solo puede importar estos módulos: `math`,
  `random` (con un generador propio), `collections`, `itertools`,
  `functools`, `heapq`, `bisect`, `copy`, `dataclasses`, `enum`, `typing` y
  `numpy`. No puede importar el paquete `pong` (ni el motor ni los bots de
  referencia) ni `pong_ref_bots`, ni usar ficheros, red, subprocesos o
  `eval`/`exec`. `runner`, `evaluate` y los tests (`tests/test_normas.py`)
  revisan `src/pong/bot.py` antes de jugar y te dicen en qué línea está el
  problema; la evaluación oficial hace la misma comprobación. Las normas
  exactas están en `src/pong/normas.py`. **Un bot que no supera esta
  comprobación invalida la práctica**: queda suspensa y hay que recuperarla.
- Límites de tiempo:
  - 50 ms por llamada: si se supera, ese tick cuenta como `STAY`.
  - 2 ms de media por llamada en toda la partida: si se supera, pierdes la
    partida (0 puntos). Desde la llamada 5 000 se vigila la media y la
    partida se corta en cuanto la supera.
  - 1 s sin responder: pierdes la partida.

  Procura no pasar de **1 ms de media** en `evaluate`: la máquina de la
  evaluación oficial puede ser más lenta que tu Codespace. `evaluate` aplica
  el límite de 2 ms y te avisa a partir de 1 ms; `runner` juega la partida
  entera y solo avisa. Un bot razonable tarda entre 0,005 y 0,05 ms.
- Si `Bot(seed)` lanza una excepción, pierdes la partida sin jugarla. Si
  `decide` lanza una excepción o devuelve otra cosa, ese tick cuenta como
  `STAY`.
- NumPy usa rutinas distintas en PC y en Mac. Un bot que lo use puede decidir
  distinto en casos límite, y su porcentaje local puede diferir ligeramente
  del oficial.

## 5. Estructura

```
src/pong/
├── bot.py           ← tu bot
├── pong_engine.py   motor del juego (no modificar)
├── bots_ref/        bots de referencia: Easy (con código) y Medium/Hard
├── registro.py      partidas con registro (CSV y JSON)
├── analisis.py      apoyo del notebook de análisis (no modificar)
├── normas.py        qué puede usar tu bot (no modificar)
├── runner.py        una partida
└── evaluate.py      evaluación contra un bot de referencia
tests/
├── test_bot.py      ← tus tests (amplíalos)
├── test_notebook.py tests de forma del notebook (no los modifiques)
└── engine/          tests del motor
notebook/
├── analisis_mo.py   ← tu notebook de análisis (Marimo)
├── ejemplo.json     partida de ejemplo
├── ejemplo.html     el notebook de ejemplo, con las figuras de la solución
└── raras/           partidas raras: abandono, con nulo y cortada por tiempo
mis_bots/            versiones anteriores de tu bot, para pong.html (no se entregan)
pong.html            visualización en el navegador
vendor/              bots Medium y Hard compilados
```

## Licencia

MIT. Véase [LICENSE](LICENSE).
