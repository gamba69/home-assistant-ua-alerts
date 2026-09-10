"""Load pure integration modules without importing Home Assistant package init."""
from __future__ import annotations

import importlib
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "ua_alerts"
PKG = "ua_alerts_core_test"


def load(name: str):
    if PKG not in sys.modules:
        package = types.ModuleType(PKG)
        package.__path__ = [str(INTEGRATION)]
        package.__package__ = PKG
        sys.modules[PKG] = package
    return importlib.import_module(f"{PKG}.{name}")
