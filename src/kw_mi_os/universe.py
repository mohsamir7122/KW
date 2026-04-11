from __future__ import annotations

from pathlib import Path

from .contracts import TradableEntity
from .models import EntityType, ListingStatus, UniverseRecord
from .validation import validate_universe


def load_universe(path: str | Path) -> list[UniverseRecord]:
    return validate_universe(path)


def load_tradable_universe(path: str | Path) -> list[UniverseRecord]:
    rows = validate_universe(path)
    return [
        row for row in rows
        if row.entity_type == EntityType.kuwait_listed_equity
        and row.listing_status == ListingStatus.listed
        and row.tradable_flag
    ]


def load_tradable_entities(path: str | Path) -> list[TradableEntity]:
    return [
        TradableEntity(
            symbol=r.symbol,
            english_name=r.english_name,
            sector=r.sector,
            market=r.market,
        )
        for r in load_tradable_universe(path)
    ]
