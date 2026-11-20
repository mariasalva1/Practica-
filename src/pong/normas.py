"""Comprobación de las normas del bot: qué puede usar ``bot.py``.

Enunciado de la práctica, apartado 3.4.

Tu bot debe ser tuyo: no puede importar los bots de referencia (ni ningún
otro módulo del paquete ``pong``), ni el motor, ni usar ficheros, red o
subprocesos. Este módulo revisa el código fuente de ``bot.py`` sin
ejecutarlo; lo usan ``runner``, ``evaluate``, los tests y la evaluación
oficial. Si tu bot no cumple, esas herramientas se niegan a jugar y te dicen
en qué línea está el problema.

Normas:

- solo se pueden importar los módulos de :data:`MODULOS_PERMITIDOS`
  (``import x``, ``import x as y`` o ``from x import y``; nada de
  importaciones relativas);
- no se pueden usar los nombres de :data:`NOMBRES_PROHIBIDOS`, que dan acceso
  a otros módulos, a ficheros o a la ejecución de código en texto;
- de los nombres con doble subrayado (``__x__``) solo se pueden usar los de
  :data:`DUNDER_PERMITIDOS` (los métodos especiales de una clase);
- los atributos que empiezan por ``_`` solo se pueden usar sobre ``self`` o
  ``cls`` (``self._historial`` sí; ``random._os`` no).

Es una comprobación estática: detecta los usos normales y la mayoría de los
rebuscados, no todos. El profesor revisa además el código de cada bot.
"""

from __future__ import annotations

import ast
from pathlib import Path

__all__ = [
    "DUNDER_PERMITIDOS",
    "MODULOS_PERMITIDOS",
    "NOMBRES_PROHIBIDOS",
    "comprobar_bot",
    "comprobar_clase",
    "infracciones",
]

RUTA_BOT = Path(__file__).with_name("bot.py")

MODULOS_PERMITIDOS = frozenset(
    {
        "__future__",
        "bisect",
        "collections",
        "copy",
        "dataclasses",
        "enum",
        "functools",
        "heapq",
        "itertools",
        "math",
        "numpy",
        "random",
        "typing",
    }
)

NOMBRES_PROHIBIDOS = frozenset(
    {
        # Acceso a otros módulos o al intérprete
        "sys",
        "os",
        "modules",
        "builtins",
        "bltns",
        "importlib",
        "inspect",
        "ctypes",
        "ctypeslib",
        "f2py",
        "testing",
        "subprocess",
        "socket",
        # Ejecución de código escrito en texto o acceso indirecto a atributos
        "eval",
        "exec",
        "compile",
        "getattr",
        "setattr",
        "delattr",
        "globals",
        "locals",
        "vars",
        "breakpoint",
        "get_type_hints",
        "attrgetter",
        "methodcaller",
        "singledispatch",
        "singledispatchmethod",
        "ForwardRef",
        # Entrada y salida
        "open",
        "input",
        "load",
        "save",
        "savez",
        "savez_compressed",
        "loadtxt",
        "savetxt",
        "genfromtxt",
        "fromfile",
        "tofile",
        "memmap",
        "DataSource",
    }
)

DUNDER_PERMITIDOS = frozenset(
    {
        "__init__",
        "__post_init__",
        "__name__",
        "__doc__",
        "__repr__",
        "__str__",
        "__eq__",
        "__ne__",
        "__lt__",
        "__le__",
        "__gt__",
        "__ge__",
        "__hash__",
        "__bool__",
        "__len__",
        "__iter__",
        "__next__",
        "__contains__",
        "__getitem__",
        "__setitem__",
        "__call__",
        "__add__",
        "__sub__",
        "__mul__",
        "__truediv__",
        "__floordiv__",
        "__mod__",
        "__pow__",
        "__neg__",
        "__pos__",
        "__abs__",
        "__radd__",
        "__rsub__",
        "__rmul__",
        "__rtruediv__",
        "__iadd__",
        "__isub__",
        "__imul__",
    }
)


def _es_dunder(nombre: str) -> bool:
    return len(nombre) > 4 and nombre.startswith("__") and nombre.endswith("__")


def infracciones(fuente: str) -> list[str]:
    """Infracciones de las normas en el código fuente de un bot.

    Args:
        fuente: el texto de ``bot.py``.

    Returns:
        Un mensaje por infracción, con su línea (vacía si cumple). Si el
        código no es Python válido, devuelve un único mensaje con el error.
    """
    try:
        arbol = ast.parse(fuente)
    except SyntaxError as error:
        return [f"línea {error.lineno}: error de sintaxis ({error.msg})"]
    permitidos = ", ".join(sorted(MODULOS_PERMITIDOS - {"__future__"}))
    mensajes = []

    def anotar(nodo: ast.AST, texto: str) -> None:
        mensajes.append(f"línea {nodo.lineno}: {texto}")

    def modulo_permitido(nombre: str) -> bool:
        return nombre.split(".")[0] in MODULOS_PERMITIDOS

    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                if not modulo_permitido(alias.name):
                    anotar(
                        nodo, f"importa {alias.name} (solo se permiten {permitidos})"
                    )
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level > 0 or nodo.module is None:
                anotar(nodo, "importación relativa (no se permiten)")
            elif not modulo_permitido(nodo.module):
                anotar(nodo, f"importa {nodo.module} (solo se permiten {permitidos})")
            for alias in nodo.names:
                if alias.name in NOMBRES_PROHIBIDOS:
                    anotar(nodo, f"importa {alias.name}, que no se permite")
        elif isinstance(nodo, ast.Name):
            if nodo.id in NOMBRES_PROHIBIDOS:
                anotar(nodo, f"usa {nodo.id}, que no se permite")
            elif _es_dunder(nodo.id) and nodo.id not in DUNDER_PERMITIDOS:
                anotar(nodo, f"usa {nodo.id}, que no se permite")
        elif isinstance(nodo, ast.Attribute):
            nombre = nodo.attr
            if nombre in NOMBRES_PROHIBIDOS:
                anotar(nodo, f"usa .{nombre}, que no se permite")
            elif _es_dunder(nombre):
                if nombre not in DUNDER_PERMITIDOS:
                    anotar(nodo, f"usa .{nombre}, que no se permite")
            elif nombre.startswith("_") and not (
                isinstance(nodo.value, ast.Name) and nodo.value.id in ("self", "cls")
            ):
                anotar(
                    nodo,
                    f"usa .{nombre}: los atributos con _ solo sobre self o cls",
                )
    return sorted(set(mensajes), key=lambda m: int(m.split()[1].rstrip(":")))


def comprobar_bot(ruta: Path = RUTA_BOT) -> list[str]:
    """Infracciones de las normas en el fichero del bot (por defecto, el tuyo)."""
    return infracciones(Path(ruta).read_text(encoding="utf-8"))


def comprobar_clase(clase: type, modulo: str = "pong.bot") -> list[str]:
    """Comprueba que ``Bot`` es una clase definida en tu ``bot.py``.

    Detecta, por ejemplo, ``Bot = OtraClase`` con una clase de otro módulo.
    """
    if not isinstance(clase, type):
        return ["Bot no es una clase"]
    if clase.__module__ != modulo:
        return [f"Bot es la clase {clase.__qualname__} de {clase.__module__}"]
    return []
