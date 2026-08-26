from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class BotState:
    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.deployment_file = self.state_dir / "deployment.json"
        self.feedback_file = self.state_dir / "feedback.jsonl"
        self.archive_file = self.state_dir / "vk_archive.json"
        self._lock = threading.Lock()

    def has_announced(self, version: str) -> bool:
        state = self._read_deployment_state()
        return state.get("announced_version") == version

    def mark_announced(self, version: str) -> None:
        payload = {
            "announced_version": version,
            "announced_at": datetime.now(UTC).isoformat(),
        }
        self._write_json_atomic(self.deployment_file, payload)

    def read_archive_state(self) -> dict[str, Any]:
        if not self.archive_file.exists():
            return {}
        try:
            value = json.loads(self.archive_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def write_archive_state(self, payload: dict[str, Any]) -> None:
        self._write_json_atomic(self.archive_file, payload)

    def add_feedback(
        self,
        *,
        text: str,
        user_id: int,
        username: str | None,
        full_name: str,
        chat_id: int,
        chat_type: str,
        message_id: int,
        bot_version: str,
    ) -> str:
        feedback_id = uuid.uuid4().hex[:10]
        record = {
            "id": feedback_id,
            "created_at": datetime.now(UTC).isoformat(),
            "bot_version": bot_version,
            "user": {
                "id": user_id,
                "username": username,
                "full_name": full_name,
            },
            "chat": {
                "id": chat_id,
                "type": chat_type,
            },
            "message_id": message_id,
            "text": text,
        }
        line = json.dumps(record, ensure_ascii=False)
        with self._lock:
            with self.feedback_file.open("a", encoding="utf-8") as output:
                output.write(f"{line}\n")
        return feedback_id

    def has_feedback(self) -> bool:
        return self.feedback_file.exists() and self.feedback_file.stat().st_size > 0

    def _write_json_atomic(self, target_file: Path, payload: dict[str, Any]) -> None:
        temporary_file = target_file.with_suffix(".tmp")
        temporary_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_file.replace(target_file)

    def _read_deployment_state(self) -> dict[str, Any]:
        if not self.deployment_file.exists():
            return {}
        try:
            value = json.loads(self.deployment_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}
