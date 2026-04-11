from __future__ import annotations

from dataclasses import dataclass

CONTEXT_SYMBOLS = {'ALL', 'MACRO', 'MKT', 'BRENT'}


@dataclass(frozen=True)
class ResolutionResult:
    input_value: str
    canonical_symbol: str | None
    status: str
    reason: str


def normalize_symbol(raw: str) -> str:
    return raw.strip().upper().replace('.KW', '')


def resolve_to_canonical_symbol(raw: str, known_symbols: set[str], aliases: dict[str, str] | None = None) -> ResolutionResult:
    symbol = normalize_symbol(raw)
    alias_map = {normalize_symbol(k): normalize_symbol(v) for k, v in (aliases or {}).items()}

    if symbol in CONTEXT_SYMBOLS:
        return ResolutionResult(raw, None, 'rejected', 'context_entity')

    if symbol in alias_map:
        symbol = alias_map[symbol]

    if symbol in known_symbols:
        return ResolutionResult(raw, symbol, 'accepted', 'canonical_match')
    return ResolutionResult(raw, None, 'rejected', 'unknown_symbol')
