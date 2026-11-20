"""Tests de los bots de referencia y de runner, evaluate y registro."""

import csv
import json
import time
from datetime import datetime

import pytest

from pong import evaluate, registro, runner
from pong import pong_engine as pe
from pong.bots_ref import NOMBRES, Easy, rival
from pong.registro import (
    COLUMNAS_CSV,
    COLUMNAS_VERDAD,
    codificar_comandos,
    csv_desde_json,
    decodificar_comandos,
    guardar_csv,
    guardar_json,
    jugar_partida,
    reproducir,
    verdad,
    verdad_csv,
)


class Explota:
    def __init__(self, seed: int) -> None:
        raise RuntimeError("constructor roto")


class Lento(Easy):
    """Easy, pero cada llamada tarda 3 ms: supera el límite medio de 2 ms."""

    def decide(self, state: dict) -> str:
        time.sleep(0.003)
        return super().decide(state)


@pytest.fixture
def corte_rapido(monkeypatch):
    """Vigila la media desde la llamada 20 en lugar de la 5 000."""
    monkeypatch.setattr(registro, "LLAMADAS_CORTE", 20)


# --- bots de referencia -----------------------------------------------------


@pytest.mark.parametrize("nombre", NOMBRES)
def test_rivales_disponibles_y_validos(nombre):
    clase = rival(nombre)
    a, b = clase(1), clase(2)
    m = pe.Match(9)
    for _ in range(1500):
        ca, cb = a.decide(m.state_for(pe.LEFT)), b.decide(m.state_for(pe.RIGHT))
        assert ca in {"UP", "DOWN", "STAY"} and cb in {"UP", "DOWN", "STAY"}
        m.step(ca, cb)


def test_rival_desconocido():
    with pytest.raises(ValueError):
        rival("imposible")


def test_medium_y_hard_estan_compilados():
    import pong_ref_bots._bots as bots

    assert not bots.__file__.endswith(".py")


# --- registro ------------------------------------------------------------------


def test_codificacion_de_comandos():
    cmds = [(a, b) for a in ("UP", "STAY", "DOWN") for b in ("UP", "STAY", "DOWN")]
    assert decodificar_comandos(codificar_comandos(cmds)) == cmds
    assert codificar_comandos(cmds) == "012345678"


def test_json_reproduce_la_partida(tmp_path):
    p = jugar_partida(5, Easy, rival("medium"), ("easy", "medium"))
    ruta = guardar_json(p, tmp_path / "partida_5.json")
    datos = json.loads(ruta.read_text())
    assert datos["result"] == p.match.result
    assert len(datos["commands"]) == p.match.tick
    assert reproducir(ruta).snapshot() == p.match.snapshot()


def test_csv_una_fila_por_tick(tmp_path):
    p = jugar_partida(6, Easy, Easy, filas=True)
    ruta = guardar_csv(p, tmp_path / "partida_6.csv")
    with open(ruta, newline="") as f:
        filas = list(csv.reader(f))
    assert tuple(filas[0]) == COLUMNAS_CSV
    assert len(filas) - 1 == p.match.tick
    assert filas[1][0] == "0" and filas[1][1] == "serving"


def test_constructor_que_falla_pierde_sin_jugar():
    p = jugar_partida(7, Explota, Easy)
    assert p.abandono == "left" and p.resultado == "right"
    assert p.comandos == [] and p.puntos("left") == (0, 0)


def test_cronometro():
    p = jugar_partida(8, Easy, Easy, cronometrar=True)
    assert p.cronos[0].llamadas == p.cronos[1].llamadas == p.match.tick
    assert p.cronos[0].media_ms >= 0.0


def test_limites_de_tiempo_de_d50():
    assert registro.LIMITE_MEDIA_MS == 2.0 and registro.AVISO_MEDIA_MS == 1.0
    assert registro.LLAMADAS_CORTE == 5000 and registro.LIMITE_LLAMADA_S == 0.050


def test_cronometro_excede():
    c = registro.Cronometro()
    for _ in range(4):
        c.anotar(0.0019)
    assert not c.excede(2.0)
    c.anotar(0.0030)  # media 2,12 ms
    assert c.excede(2.0)


@pytest.mark.parametrize("lado", ["left", "right"])
def test_bot_lento_corta_la_partida(corte_rapido, lado):
    izq, der = (Lento, Easy) if lado == "left" else (Easy, Lento)
    p = jugar_partida(5, izq, der, limite_media_ms=2.0)
    assert p.tiempo_excedido == lado
    assert p.resultado == ("right" if lado == "left" else "left")
    assert p.puntos("left") == p.puntos("right") == (0, 0)
    assert len(p.comandos) == 20 and not p.match.over


def test_bot_rapido_no_se_corta(corte_rapido):
    p = jugar_partida(5, Easy, Easy, limite_media_ms=2.0)
    assert p.tiempo_excedido is None and p.match.over


class LentoAlPrincipio(Easy):
    """Tarda 3 ms en sus 30 primeras llamadas y luego es rápido."""

    def __init__(self, seed: int) -> None:
        super().__init__(seed)
        self.n = 0

    def decide(self, state: dict) -> str:
        self.n += 1
        if self.n <= 30:
            time.sleep(0.003)
        return super().decide(state)


def test_sin_limite_no_se_corta(corte_rapido):
    p = jugar_partida(5, LentoAlPrincipio, Easy, cronometrar=True)
    assert p.tiempo_excedido is None and p.match.over
    p = jugar_partida(5, LentoAlPrincipio, Easy, limite_media_ms=2.0)
    assert p.tiempo_excedido == "left" and len(p.comandos) == 20


def test_partida_cortada_se_graba_y_se_reproduce(corte_rapido, tmp_path):
    p = jugar_partida(5, Lento, Easy, ("lento", "easy"), limite_media_ms=2.0)
    ruta = guardar_json(p, tmp_path / "partida_5.json")
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["tiempo_excedido"] == "left" and datos["result"] == "right"
    assert len(datos["commands"]) == 20
    assert reproducir(ruta).tick == 20
    with open(csv_desde_json(ruta), newline="") as f:
        assert len(list(csv.reader(f))) == 1 + 20


def test_json_de_partida_normal_sin_tiempo_excedido(tmp_path):
    p = jugar_partida(3, Easy, Easy)
    datos = json.loads(guardar_json(p, tmp_path / "p.json").read_text())
    assert datos["tiempo_excedido"] is None


# --- evaluate y runner -------------------------------------------------------


@pytest.mark.parametrize(
    "rival_nombre, puntos, nota",
    [
        ("easy", 0.5, 0.0),
        ("easy", 0.9, 1.0),
        ("easy", 0.7, 0.5),
        ("easy", 0.85, 0.875),
        ("medium", 0.2, 0.0),
        ("medium", 0.575, 0.5),
        ("medium", 0.55, 0.4),
        ("hard", 0.40, 1.5 * 5 / 13),
        ("hard", 0.48, 1.5),
        ("hard", 1.0, 1.5),
    ],
)
def test_nota_componente(rival_nombre, puntos, nota):
    assert evaluate.nota_componente(rival_nombre, puntos) == pytest.approx(nota)


def test_pesos_de_rendimiento_suman_3_5():
    assert evaluate.PESOS == {"easy": 1.0, "medium": 1.0, "hard": 1.5}
    assert sum(evaluate.PESOS.values()) == 3.5


def test_evaluar_alterna_lados_y_resume():
    r = evaluate.evaluar("easy", 2, semilla_base=100)
    assert r.partidas == 2
    assert 0.0 <= r.puntos <= 1.0
    assert r.cronometro.llamadas > 0


def test_carpeta_ejecucion_nueva_en_cada_ejecucion(tmp_path):
    momento = datetime(2026, 11, 3, 10, 15)
    c1 = evaluate.carpeta_ejecucion(tmp_path, "hard", momento)
    assert c1 == tmp_path / "evaluate_hard_2026-11-03_1015"
    c1.mkdir()
    c2 = evaluate.carpeta_ejecucion(tmp_path, "hard", momento)
    assert c2 == tmp_path / "evaluate_hard_2026-11-03_1015_2"


def test_evaluar_guarda_registros_y_resumen(tmp_path):
    carpeta = tmp_path / "evaluate_easy"
    r = evaluate.evaluar("easy", 4, semilla_base=200, guardar=carpeta)
    for s in range(200, 204):
        assert (carpeta / f"partida_{s}.json").exists()
    with open(carpeta / "resumen.csv", newline="") as f:
        filas = list(csv.DictReader(f))
    assert tuple(filas[0]) == evaluate.COLUMNAS_RESUMEN
    assert len(filas) == 4
    puntos = [float(f["puntos"]) for f in filas]
    assert puntos == sorted(puntos)  # de la peor a la mejor
    for f in filas:
        lado = "left" if f["lado"] == "izquierda" else "right"
        assert lado == ("left" if int(f["semilla"]) % 2 == 0 else "right")
        assert f["registro"] == f"partida_{f['semilla']}.json"
    assert sum(puntos) / 4 == pytest.approx(r.puntos, abs=1e-4)


def test_evaluar_sin_guardar_no_escribe(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    evaluate.evaluar("easy", 2, semilla_base=300)
    assert list(tmp_path.iterdir()) == []


def test_evaluate_main_con_guardar(tmp_path, capsys):
    args = ["--rival", "easy", "--partidas", "2", "--semilla-base", "400"]
    assert evaluate.main([*args, "--guardar", "--salida", str(tmp_path)]) == 0
    (carpeta,) = tmp_path.iterdir()
    assert carpeta.name.startswith("evaluate_easy_")
    assert (carpeta / "resumen.csv").exists()
    salida = capsys.readouterr().out
    assert "Tus peores partidas" in salida and "partida_40" in salida


def test_evaluar_bot_lento_pierde_por_tiempo(monkeypatch, corte_rapido, capsys):
    monkeypatch.setattr(evaluate, "cargar_mi_bot", lambda: Lento)
    r = evaluate.evaluar("easy", 2, semilla_base=0)
    assert r.por_tiempo == 2 and r.puntos == 0.0
    assert [p.resultado for p in r.detalle] == ["tiempo", "tiempo"]
    assert r.derrotas == 2


def test_evaluate_main_avisa_del_tiempo(monkeypatch, corte_rapido, capsys):
    monkeypatch.setattr(evaluate, "cargar_mi_bot", lambda: Lento)
    evaluate.main(["--rival", "easy", "--partidas", "2", "--semilla-base", "0"])
    assert "2 partidas perdidas (0 puntos)" in capsys.readouterr().out


def test_evaluar_constructor_roto(monkeypatch):
    monkeypatch.setattr(evaluate, "cargar_mi_bot", lambda: Explota)
    r = evaluate.evaluar("easy", 2, semilla_base=0)
    assert (r.victorias, r.empates, r.derrotas) == (0, 0, 2)
    assert r.puntos == 0.0


def test_runner_escribe_solo_el_json_por_defecto(tmp_path, capsys):
    assert (
        runner.main(["--rival", "easy", "--semilla", "3", "--salida", str(tmp_path)])
        == 0
    )
    assert (tmp_path / "partida_3.json").exists()
    assert not (tmp_path / "partida_3.csv").exists()
    assert "Resultado" in capsys.readouterr().out


def test_runner_con_csv(tmp_path, capsys):
    args = ["--rival", "easy", "--semilla", "3", "--salida", str(tmp_path), "--csv"]
    assert runner.main(args) == 0
    assert (tmp_path / "partida_3.json").exists()
    assert (tmp_path / "partida_3.csv").exists()


# --- CSV regenerado desde el JSON ----------------------------------------------


@pytest.mark.parametrize("rival_derecho", ["easy", "hard"])
def test_csv_desde_json_identico_al_de_la_partida(tmp_path, rival_derecho):
    p = jugar_partida(11, Easy, rival(rival_derecho), filas=True)
    original = guardar_csv(p, tmp_path / "jugada.csv")
    ruta_json = guardar_json(p, tmp_path / "partida_11.json")
    regenerado = csv_desde_json(ruta_json)
    assert regenerado == tmp_path / "partida_11.csv"
    assert regenerado.read_bytes() == original.read_bytes()


def test_csv_desde_json_con_ruta_de_salida(tmp_path):
    p = jugar_partida(12, Easy, Easy)
    ruta_json = guardar_json(p, tmp_path / "partida_12.json")
    destino = csv_desde_json(ruta_json, tmp_path / "otra" / "datos.csv")
    with open(destino, newline="") as f:
        filas = list(csv.reader(f))
    assert tuple(filas[0]) == COLUMNAS_CSV
    assert len(filas) - 1 == p.match.tick


def test_csv_desde_json_de_una_partida_no_jugada(tmp_path):
    p = jugar_partida(13, Easy, Explota)
    ruta = csv_desde_json(guardar_json(p, tmp_path / "partida_13.json"))
    assert ruta.read_text().splitlines() == [",".join(COLUMNAS_CSV)]


def test_csv_desde_json_rechaza_otra_version_del_motor(tmp_path):
    p = jugar_partida(14, Easy, Easy)
    ruta = guardar_json(p, tmp_path / "partida_14.json")
    datos = json.loads(ruta.read_text())
    datos["engine_version"] = "0.9"
    ruta.write_text(json.dumps(datos))
    with pytest.raises(ValueError, match="versión 0.9"):
        csv_desde_json(ruta)


def test_csv_solo_columnas_observables():
    # El CSV tiene lo que ven los bots; velocidades y efecto van aparte
    assert not {"ball_vx", "ball_vy", "ball_ay", "ball_speed"} & set(COLUMNAS_CSV)
    assert "server" in COLUMNAS_CSV


def test_verdad_coincide_con_el_motor(tmp_path):
    p = jugar_partida(17, Easy, rival("hard"))
    ruta = guardar_json(p, tmp_path / "partida_17.json")
    filas = verdad(ruta)
    assert len(filas) == p.match.tick
    assert tuple(filas[0]) == COLUMNAS_VERDAD
    m = pe.Match(17)
    comandos = decodificar_comandos(json.loads(ruta.read_text())["commands"])
    for t, (izq, der) in enumerate(comandos):
        if t % 997 == 0:
            s = m.snapshot()
            assert filas[t] == {
                "tick": t,
                "ball_vx": s["ball_vx"],
                "ball_vy": s["ball_vy"],
                "ball_ay": s["ball_ay"],
                "ball_speed": s["ball_speed"],
            }
        m.step(izq, der)


def test_verdad_es_la_diferencia_de_posiciones(tmp_path):
    """y_t − y_(t−1) = vy_t en los ticks de vuelo sin golpe ni rebote."""
    p = jugar_partida(18, rival("hard"), Easy, filas=True)
    ruta = guardar_json(p, tmp_path / "partida_18.json")
    ver = verdad(ruta)
    filas = p.filas
    i_y, i_estado, i_golpes = (
        COLUMNAS_CSV.index(c) for c in ("ball_y", "state", "rally_hits")
    )
    comprobados = 0
    for t in range(1, len(filas)):
        ant, act = filas[t - 1], filas[t]
        if ant[i_estado] != "playing" or act[i_estado] != "playing":
            continue
        if act[i_golpes] != ant[i_golpes]:
            continue  # golpe: la bola se recoloca en la cara frontal
        if (ver[t]["ball_vy"] > 0) != (ver[t - 1]["ball_vy"] > 0):
            continue  # rebote en una pared
        assert act[i_y] - ant[i_y] == pytest.approx(ver[t]["ball_vy"], abs=1e-9)
        comprobados += 1
    assert comprobados > 1000


def test_verdad_csv_junto_al_json(tmp_path):
    p = jugar_partida(19, Easy, Easy)
    ruta = verdad_csv(guardar_json(p, tmp_path / "partida_19.json"))
    assert ruta == tmp_path / "partida_19_verdad.csv"
    with open(ruta, newline="") as f:
        filas = list(csv.reader(f))
    assert tuple(filas[0]) == COLUMNAS_VERDAD
    assert len(filas) - 1 == p.match.tick


def test_orden_registro(tmp_path, capsys):
    rutas = [
        guardar_json(jugar_partida(s, Easy, Easy), tmp_path / f"partida_{s}.json")
        for s in (15, 16)
    ]
    assert registro.main([str(r) for r in rutas]) == 0
    assert (tmp_path / "partida_15.csv").exists()
    assert (tmp_path / "partida_16.csv").exists()
    assert not (tmp_path / "partida_15_verdad.csv").exists()
    assert registro.main([str(rutas[0]), "--verdad"]) == 0
    assert (tmp_path / "partida_15_verdad.csv").exists()
    assert registro.main([str(tmp_path / "no_existe.json")]) == 1
    assert "No se pudo convertir" in capsys.readouterr().err
