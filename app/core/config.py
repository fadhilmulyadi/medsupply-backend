from pathlib import Path
from typing import Any, Dict
import json


def load_config(path: str = "data/config.json") -> Dict[str, Any]:
    """
    Memuat konfigurasi JSON yang berisi bobot, batasan, dan pengaturan lainnya.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found at {config_path.resolve()}")

    with config_path.open("r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)

    return data
