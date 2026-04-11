from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen
import json

from .models import SourceClass


@dataclass(frozen=True)
class SourceCatalogEntry:
    source: str
    source_class: SourceClass
    url: str
    timeout_sec: int = 8


@dataclass(frozen=True)
class FetchResult:
    source: str
    status: str
    http_status: int | None
    payload: dict[str, Any] | None
    error: str | None


def fetch_json(entry: SourceCatalogEntry, retries: int = 2) -> FetchResult:
    last_error: str | None = None
    for _ in range(retries + 1):
        try:
            with urlopen(entry.url, timeout=entry.timeout_sec) as resp:  # noqa: S310
                status = getattr(resp, 'status', 200)
                if status >= 400:
                    last_error = f'http_{status}'
                    continue
                body = resp.read().decode('utf-8')
                return FetchResult(entry.source, 'ok', status, json.loads(body), None)
        except (URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            last_error = str(exc)
    return FetchResult(entry.source, 'fallback_unavailable', None, None, last_error)


def default_source_catalog() -> list[SourceCatalogEntry]:
    return [
        SourceCatalogEntry('official_exchange_status', SourceClass.official_exchange, 'https://httpbin.org/json'),
        SourceCatalogEntry('macro_context_probe', SourceClass.macro_context_only, 'https://httpbin.org/status/503'),
    ]
