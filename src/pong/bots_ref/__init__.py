"""Bots de referencia (enunciado, apartado 3.5).

- ``Easy``: código fuente en ``easy.py``.
- ``Medium`` y ``Hard``: compilados, en el paquete ``pong_ref_bots`` (rueda en
  ``vendor/``). Solo funcionan en los entornos soportados: Codespaces o Dev
  Container en Linux x86-64 o ARM64.
"""

from __future__ import annotations

from collections.abc import Callable

from .easy import Easy

try:
    from pong_ref_bots import Hard, Medium
except ImportError:  # entorno no soportado
    Medium = None
    Hard = None

NOMBRES = ("easy", "medium", "hard")


def rival(nombre: str) -> Callable[[int], object]:
    """Devuelve la clase del bot de referencia ``nombre``.

    Raises:
        ValueError: si el nombre no es ``easy``, ``medium`` ni ``hard``.
        RuntimeError: si Medium o Hard no están disponibles en este entorno.
    """
    clases = {"easy": Easy, "medium": Medium, "hard": Hard}
    if nombre not in clases:
        raise ValueError(f"rival desconocido: {nombre!r}; usa {', '.join(NOMBRES)}")
    clase = clases[nombre]
    if clase is None:
        raise RuntimeError(
            f"El bot {nombre!r} no está disponible: trabaja en Codespaces o en el "
            "Dev Container (Linux x86-64 o ARM64) y ejecuta 'uv sync'."
        )
    return clase
