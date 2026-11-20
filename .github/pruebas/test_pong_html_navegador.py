"""Prueba de pong.html en un navegador real (Chromium con Playwright).

Solo la ejecuta la CI de la plantilla (trabajo «pong.html»); los alumnos no la
necesitan. En local:

    uv run --with playwright==1.56.0 python -m playwright install chromium
    uv run --with playwright==1.56.0 python -m pytest .github/pruebas

Pyodide se descarga de la CDN, como en la página. Sin acceso a la CDN, la
variable ``PONG_PYODIDE_LOCAL`` puede apuntar a una copia local de la
distribución (por ejemplo, el paquete ``pyodide`` de npm).

Lo esencial es la comparación bit a bit: la partida jugada en el navegador
(motor en Pyodide) produce exactamente el mismo registro JSON que la misma
partida jugada con CPython.
"""

from __future__ import annotations

import contextlib
import functools
import http.server
import io
import json
import os
import shutil
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from pong import evaluate, registro  # noqa: E402
from pong.bots_ref import Easy, Hard  # noqa: E402
from pong.registro import guardar_json, jugar_partida  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
TIEMPO_CARGA_MS = 180_000

BOT_PRUEBA = '''\
"""Bot de prueba: sigue la bola, dibuja, imprime y falla de vez en cuando."""


class Bot:
    def __init__(self, seed):
        self.n = 0

    def decide(self, state):
        self.n += 1
        if self.n % 500 == 0:
            print("tick", state["tick"])
        if self.n % 1000 == 0:
            raise ValueError("fallo de prueba")
        y = state["ball_y"]
        trayectoria = [(state["ball_x"], y), (30, y)]
        self.depuracion = {"objetivo_y": y, "trayectoria": trayectoria}
        if self.n % 700 == 0:
            return "up"
        d = y - state["my_paddle_y"]
        return "DOWN" if d > 4 else "UP" if d < -4 else "STAY"
'''

BOT_ROTO = """\
class Bot:
    def __init__(self, seed):
        raise RuntimeError("constructor roto")

    def decide(self, state):
        return "STAY"
"""


class Lento(Easy):
    def decide(self, state):
        time.sleep(0.003)
        return super().decide(state)


def _clase(codigo: str) -> type:
    espacio: dict = {}
    exec(codigo, espacio)
    return espacio["Bot"]


@pytest.fixture(scope="module")
def sitio(tmp_path_factory) -> Path:
    """Copia de la raíz servible, con mis_bots/ y partidas/ de prueba."""
    d = tmp_path_factory.mktemp("sitio")
    shutil.copy(RAIZ / "pong.html", d / "pong.html")
    shutil.copytree(RAIZ / "src", d / "src")
    (d / "mis_bots").mkdir()
    (d / "mis_bots" / "prueba.py").write_text(BOT_PRUEBA, encoding="utf-8")
    (d / "mis_bots" / "roto.py").write_text(BOT_ROTO, encoding="utf-8")
    partida = jugar_partida(7, Hard, Easy, ("hard", "easy"))
    guardar_json(partida, d / "partidas" / "partida_7.json")
    evaluate.evaluar(
        "hard", 3, semilla_base=20, guardar=d / "partidas" / "evaluate_hard_prueba"
    )
    corte = registro.LLAMADAS_CORTE
    registro.LLAMADAS_CORTE = 20
    try:
        lenta = jugar_partida(9, Lento, Easy, ("lento", "easy"), limite_media_ms=2.0)
    finally:
        registro.LLAMADAS_CORTE = corte
    guardar_json(lenta, d / "partidas" / "partida_9.json")
    return d


@pytest.fixture(scope="module")
def url(sitio: Path) -> Iterator[str]:
    class Manejador(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args) -> None:
            pass

    servidor = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Manejador, directory=str(sitio))
    )
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    yield f"http://127.0.0.1:{servidor.server_port}/pong.html"
    servidor.shutdown()


@pytest.fixture(scope="module")
def pagina(url: str):
    local = os.environ.get("PONG_PYODIDE_LOCAL")
    with playwright.sync_playwright() as p:
        navegador = p.chromium.launch()
        pg = navegador.new_page(accept_downloads=True)
        errores: list[str] = []
        pg.on("pageerror", lambda e: errores.append(str(e)))
        if local:

            def servir_local(ruta) -> None:
                nombre = ruta.request.url.split("/full/", 1)[1].split("?")[0]
                f = Path(local) / nombre
                if f.is_file():
                    ruta.fulfill(path=str(f))
                else:
                    ruta.fulfill(status=404, body="no está en la copia local")

            pg.route("https://cdn.jsdelivr.net/pyodide/**", servir_local)
        pg.goto(url)
        pg.wait_for_function(
            "document.getElementById('estado').dataset.estado !== 'cargando'",
            timeout=TIEMPO_CARGA_MS,
        )
        pg.evaluate("window.pong.listo")
        pg.errores = errores
        yield pg
        navegador.close()


def _esperar_bots(pg, derecha: str) -> None:
    pg.wait_for_function(
        "n => window.pong.resumen() && window.pong.resumen().nombres[1] === n",
        arg=derecha,
    )


def test_carga_el_motor_del_repositorio(pagina):
    assert pagina.inner_text("#estado") == "Listo"
    assert pagina.inner_text("#version") == "motor 1.0"
    opciones = pagina.eval_on_selector_all(
        "#sel-der option", "os => os.map(o => o.value)"
    )
    assert opciones == ["mi_bot", "easy", "mis_bots/prueba.py", "mis_bots/roto.py"]


def test_partida_en_directo_identica_a_cpython(pagina, sitio, tmp_path):
    pagina.fill("#semilla", "7")
    pagina.press("#semilla", "Enter")
    pagina.select_option("#sel-izq", "easy")
    pagina.select_option("#sel-der", "mis_bots/prueba.py")
    _esperar_bots(pagina, "mis_bots/prueba")
    pagina.evaluate("window.pong.irAlFinal()")
    assert pagina.evaluate("window.pong.resumen().terminada")
    with pagina.expect_download() as descarga:
        pagina.click("#b-descargar")
    ruta = tmp_path / "navegador.json"
    descarga.value.save_as(ruta)

    with contextlib.redirect_stdout(io.StringIO()):
        partida = jugar_partida(
            7, Easy, _clase(BOT_PRUEBA), ("easy", "mis_bots/prueba")
        )
    esperado = guardar_json(partida, tmp_path / "cpython.json")
    assert ruta.read_text(encoding="utf-8") == esperado.read_text(encoding="utf-8")

    # Consola y dibujo de depuración
    assert pagina.locator("#consola .msg.error").count() > 0
    assert pagina.locator("#consola .msg.print").count() > 0
    assert pagina.locator("#consola .msg.aviso").count() > 0
    pagina.evaluate("window.pong.irA(1234)")
    dep = pagina.evaluate("window.pong.fotograma.depuracion")
    assert dep[0] is None and json.loads(dep[1])["objetivo_y"] > 0


def test_constructor_roto_pierde_sin_jugar(pagina):
    pagina.select_option("#sel-der", "mis_bots/roto.py")
    _esperar_bots(pagina, "mis_bots/roto")
    resumen = pagina.evaluate("window.pong.resumen()")
    assert resumen["abandono"] == "right" and resumen["resultado"] == "left"
    assert "constructor roto" in pagina.inner_text("#consola")


def test_reproduccion_verificada_y_manipulada(pagina, sitio):
    pagina.click("#tab-repro")
    pagina.wait_for_function(
        "document.querySelectorAll('#sel-partida option').length > 1"
    )
    pagina.select_option("#sel-partida", "partida_7.json")
    pagina.wait_for_function(
        "window.pong.resumen() && window.pong.resumen().verificacion"
    )
    assert "Reproducción verificada" in pagina.inner_text("#verificacion")

    datos = json.loads((sitio / "partidas" / "partida_7.json").read_text())
    datos["rallies"][2]["winner"] = (
        "left" if datos["rallies"][2]["winner"] == "right" else "right"
    )
    pagina.evaluate("t => window.pong.reproducir(t, 'manipulado')", json.dumps(datos))
    assert "no coincide" in pagina.inner_text("#verificacion")


def test_sin_errores_de_javascript(pagina):
    assert pagina.errores == []


def test_lista_las_ejecuciones_de_evaluate(pagina, sitio):
    pagina.click("#tab-repro")
    grupos = pagina.eval_on_selector_all(
        "#sel-partida optgroup", "gs => gs.map(g => g.label)"
    )
    assert grupos == ["partidas/", "partidas/evaluate_hard_prueba/"]
    opciones = pagina.eval_on_selector_all(
        "#sel-partida optgroup:nth-of-type(2) option", "os => os.map(o => o.value)"
    )
    carpeta = sitio / "partidas" / "evaluate_hard_prueba"
    lineas = (carpeta / "resumen.csv").read_text().splitlines()[1:]
    orden = [linea.split(",")[-1] for linea in lineas]  # de la peor a la mejor
    assert opciones == [f"evaluate_hard_prueba/{n}" for n in orden]
    pagina.select_option("#sel-partida", opciones[0])
    pagina.wait_for_function(
        "n => window.pong.resumen() && window.pong.resumen().semilla === n",
        arg=int(orden[0].removeprefix("partida_").removesuffix(".json")),
    )
    assert "Reproducción verificada" in pagina.inner_text("#verificacion")


def test_reproduccion_de_partida_cortada_por_tiempo(pagina):
    pagina.click("#tab-repro")
    pagina.wait_for_function(
        "document.querySelectorAll('#sel-partida option').length > 1"
    )
    pagina.select_option("#sel-partida", "partida_9.json")
    pagina.wait_for_function(
        "window.pong.resumen() && window.pong.resumen().semilla === 9"
    )
    texto = pagina.inner_text("#verificacion")
    assert "Reproducción verificada" in texto and "tiempo medio" in texto
    assert pagina.evaluate("window.pong.resumen().resultado") == "right"
