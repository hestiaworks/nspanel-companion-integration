"""Load one of the integration's modules without Home Assistant.

Registers the package first, so a module that imports a sibling
relatively — layout.py importing notifications.py — loads the same way
here as it does inside Home Assistant.
"""

from importlib import import_module
from pathlib import Path
import sys
import types

ROOT = Path(__file__).parents[1] / "custom_components/nspanel_companion"


if "nspanel_companion" not in sys.modules:
    package = types.ModuleType("nspanel_companion")
    package.__path__ = [str(ROOT)]
    sys.modules["nspanel_companion"] = package


def load(name: str):
    return import_module(f"nspanel_companion.{name}")
