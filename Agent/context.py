from dataclasses import dataclass, field
from typing import Dict, Any
import time
import json
import os
import uuid
from datetime import datetime


@dataclass
class Context:
    """Runtime state + temporary JSON store for each operation.

    Adds simple persistence to a `context.json` file and a journaling/log helper.
    """
    run_id: str | None = None
    start_time: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    temp_json: Dict[str, Any] = field(default_factory=dict)
    logs: list = field(default_factory=list)

    def __post_init__(self):
        if not self.run_id:
            # generate a readable run id
            self.run_id = datetime.utcnow().strftime("run_%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]

    def update(self, key: str, value: Any):
        self.metadata[key] = value

    def get(self, key: str, default=None):
        return self.metadata.get(key, default)

    def store_temp_json(self, data: Dict[str, Any]):
        self.temp_json = data

    def clear_temp_json(self):
        self.temp_json = {}

    def temp_json_str(self) -> str:
        return json.dumps(self.temp_json, indent=2)

    # ---- Persistence helpers ----
    def save_context(self, path: str = "context.json") -> None:
        payload = {
            "operation_id": self.run_id,
            "start_time": datetime.utcfromtimestamp(self.start_time).isoformat() + "Z",
            "metadata": self.metadata,
            "temp_json": self.temp_json,
            "logs": self.logs,
        }
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def load_context(self, path: str = "context.json") -> None:
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        self.run_id = payload.get("operation_id", self.run_id)
        # keep existing start_time if not provided
        try:
            self.start_time = time.mktime(datetime.fromisoformat(payload.get("start_time").replace("Z", "")).timetuple())
        except Exception:
            pass
        self.metadata.update(payload.get("metadata", {}))
        self.temp_json = payload.get("temp_json", {})
        self.logs = payload.get("logs", [])

    def append_log(self, module: str, action: str, status: str = "info", details: dict | None = None, log_path: str = "logs/penzer.log") -> None:
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "module": module,
            "action": action,
            "status": status,
            "details": details or {},
            "operation_id": self.run_id,
        }
        self.logs.append(entry)
        # ensure log directory exists
        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            # best-effort logging; don't raise
            pass
