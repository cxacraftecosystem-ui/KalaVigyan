from __future__ import annotations

from .craft_master_loader import DATA_DIR

__all__ = ["LAYERS_DIR", "LAYER_FILES", "MINERALS_FILE", "RELIEF_FILE", "RIVERS_FILE"]

LAYERS_DIR = DATA_DIR / "layers"
RELIEF_FILE = "relief.json"
RIVERS_FILE = "rivers.json"
MINERALS_FILE = "minerals.json"
LAYER_FILES = (RELIEF_FILE, RIVERS_FILE, MINERALS_FILE)
