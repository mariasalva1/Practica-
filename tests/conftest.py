"""
Configuración compartida para pytest.
La detección del paquete principal (el que está dentro de src/) es dinámica.
"""

from pathlib import Path


def _find_package():
    src_dir = Path(__file__).resolve().parents[1] / "src"
    if not src_dir.is_dir():
        return None
    for item in src_dir.iterdir():
        if item.is_dir() and (item / "__init__.py").exists():
            return item.name
    return None


PACKAGE_NAME = _find_package()


def pytest_sessionstart(session):
    if PACKAGE_NAME is None:
        print("⚠️  No se encontró ningún paquete en src/.")
    else:
        try:
            __import__(PACKAGE_NAME)
            print(f"✅ Paquete '{PACKAGE_NAME}' importado correctamente.")
        except ImportError:
            print(f"⚠️  No se pudo importar '{PACKAGE_NAME}'. Ejecuta 'uv sync'.")


def pytest_addoption(parser):
    parser.addoption(
        "--modo-verbose",
        action="store_true",
        default=False,
        help="Ejecuta los tests en modo detallado",
    )
