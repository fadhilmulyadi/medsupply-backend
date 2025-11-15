import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

_LOG_DIR = Path("logs")
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_LOG_FILE = _LOG_DIR / "audit.log"

def log_event(event_type: str, payload: Dict[str, Any], request_id: Optional[str] = None, run_id: Optional[str] = None) -> None:
    record = {
        "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "event": event_type,
        "request_id": request_id,
        "run_id": run_id,
        **payload,
    }
    try:
        with _LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass
