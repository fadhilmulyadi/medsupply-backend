import json, os, threading, time, uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Optional

def _file_signature(path: Path) -> str:
    try:
        stat = path.stat()
        return f"{path.name}:{int(stat.st_mtime)}:{stat.st_size}"
    except FileNotFoundError:
        return f"{path.name}:missing"

def compute_data_signature(
    facilities_path: str = "data/facilities.csv",
    patients_path: str = "data/patients_batch.csv",
    config_path: str = "data/config.json",
) -> str:
    f1 = _file_signature(Path(facilities_path))
    f2 = _file_signature(Path(patients_path))
    f3 = _file_signature(Path(config_path))
    return "|".join([f1, f2, f3])

@dataclass
class MatchRun:
    run_id: str
    created_at: float
    data_signature: str
    config: Dict[str, Any]
    result: Dict[str, Any]

class StateManager:
    def __init__(self, persist_dir: str = "state"):
        self._lock = threading.Lock()
        self._last_run: Optional[MatchRun] = None
        self._persist_dir = Path(persist_dir)
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._persist_file = self._persist_dir / "last_run.json"
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        try:
            if self._persist_file.exists():
                data = json.loads(self._persist_file.read_text(encoding="utf-8"))
                self._last_run = MatchRun(
                    run_id=data["run_id"],
                    created_at=float(data["created_at"]),
                    data_signature=str(data["data_signature"]),
                    config=data["config"],
                    result=data["result"],
                )
        except Exception:
            self._last_run = None

    def _save_to_disk(self) -> None:
        try:
            if self._last_run is None:
                return
            payload = asdict(self._last_run)
            self._persist_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def set_last_run(self, config: Dict[str, Any], result: Dict[str, Any], data_signature: Optional[str] = None) -> MatchRun:
        with self._lock:
            run = MatchRun(
                run_id=str(uuid.uuid4()),
                created_at=time.time(),
                data_signature=data_signature or compute_data_signature(),
                config=config,
                result=result,
            )
            self._last_run = run
            self._save_to_disk()
            return run

    def get_last_run(self) -> Optional[MatchRun]:
        with self._lock:
            return self._last_run

    def is_valid_for_current_data(self) -> bool:
        with self._lock:
            if self._last_run is None:
                return False
            return self._last_run.data_signature == compute_data_signature()

    def clear(self) -> None:
        with self._lock:
            self._last_run = None
            try:
                if self._persist_file.exists():
                    self._persist_file.unlink()
            except Exception:
                pass

# Singleton
state = StateManager()
