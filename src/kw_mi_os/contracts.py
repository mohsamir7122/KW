from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
import hashlib
import subprocess
import uuid


@dataclass(frozen=True)
class TradableEntity:
    symbol: str
    english_name: str
    sector: str
    market: str


@dataclass
class RunManifest:
    mode: str
    phase: str
    internet_fetch_status: str
    files_read: list[str]
    files_written: list[str]
    validations: list[str]
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    input_checksums: dict[str, str] = field(default_factory=dict)
    git_commit: str = field(default_factory=lambda: current_git_commit())
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def sha256_of_text(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def current_git_commit() -> str:
    try:
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('utf-8').strip()
    except Exception:  # noqa: BLE001
        return 'unknown'
