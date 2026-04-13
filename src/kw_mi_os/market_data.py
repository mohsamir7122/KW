from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import csv
import io
import json
from pathlib import Path
import re
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from .entity_resolution import normalize_symbol, resolve_to_canonical_symbol
from .models import (
    MarketDataIngestionMetadata,
    MarketDataQualityReport,
    MarketDataRow,
    MarketDataSnapshot,
    MarketSourceCatalogEntry,
    MarketSourceClass,
    MarketSourceStatus,
    UniverseRecord,
)


@dataclass(frozen=True)
class RawFetchPayload:
    source_name: str
    status_code: int | None
    body: str | None
    error: str | None


def market_source_catalog() -> list[MarketSourceCatalogEntry]:
    return [
        MarketSourceCatalogEntry(
            source_name='boursa_kuwait_market_watch',
            source_class=MarketSourceClass.priority_1_official_market,
            expected_reliability='high',
            expected_freshness='intraday_delayed',
            parsing_notes='Official page first. Attempt embedded JSON/table extraction; may be blocked by anti-bot.',
            login_notes='Public page expected; if blocked/login encountered fall back to public delayed secondary source.',
            allowed_use='price_source_of_truth',
            fallback_priority=1,
            url='https://www.boursakuwait.com.kw/en/market-watch',
            timeout_sec=10,
        ),
        MarketSourceCatalogEntry(
            source_name='boursa_kuwait_market_reports',
            source_class=MarketSourceClass.priority_2_exchange_adjacent,
            expected_reliability='high',
            expected_freshness='end_of_day_or_delayed',
            parsing_notes='Fallback official/exchange-adjacent source for last prices when market-watch parsing fails.',
            login_notes='Public report pages usually available; may change URL patterns.',
            allowed_use='price_source_of_truth',
            fallback_priority=2,
            url='https://www.boursakuwait.com.kw/en/market-information',
            timeout_sec=10,
        ),
        MarketSourceCatalogEntry(
            source_name='yahoo_finance_quote',
            source_class=MarketSourceClass.priority_3_secondary_market_data,
            expected_reliability='medium',
            expected_freshness='near_real_time_or_delayed',
            parsing_notes='Secondary fallback only. Must not silently override official rows.',
            login_notes='Public API endpoint; can throttle or block.',
            allowed_use='secondary_fallback_or_cross_check',
            fallback_priority=3,
            url='https://query1.finance.yahoo.com/v7/finance/quote',
            timeout_sec=10,
        ),
        MarketSourceCatalogEntry(
            source_name='reuters_kuwait_context',
            source_class=MarketSourceClass.priority_4_news_context,
            expected_reliability='medium',
            expected_freshness='news_cycle',
            parsing_notes='Context-only source, not used for price rows.',
            login_notes='Public news pages; may use anti-bot.',
            allowed_use='context_only_not_price_truth',
            fallback_priority=4,
            url='https://www.reuters.com/markets/',
            timeout_sec=10,
        ),
    ]


def _fetch_raw_url(url: str, timeout_sec: int, retries: int = 2) -> tuple[int | None, str | None, str | None]:
    last_error: str | None = None
    for _ in range(retries + 1):
        try:
            with urlopen(url, timeout=timeout_sec) as resp:  # noqa: S310
                status_code = getattr(resp, 'status', 200)
                body = resp.read().decode('utf-8', errors='replace')
                if status_code >= 400:
                    last_error = f'http_{status_code}'
                    continue
                return status_code, body, None
        except (URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)
    return None, None, last_error or 'unknown_error'


def _parse_float(value: str | float | int | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = value.strip().replace(',', '')
    if cleaned in {'', '-', 'N/A', 'na', 'null'}:
        return None
    return float(cleaned)


def _parse_int(value: str | int | float | None) -> int | None:
    parsed = _parse_float(value)
    if parsed is None:
        return None
    return int(parsed)


def _parse_boursa_rows(body: str, now_utc: datetime, source_name: str) -> list[MarketDataRow]:
    rows: list[MarketDataRow] = []
    if 'login' in body.lower() and 'boursa' in body.lower():
        return rows
    table_chunks = re.findall(r'<tr[^>]*>(.*?)</tr>', body, flags=re.IGNORECASE | re.DOTALL)
    for chunk in table_chunks:
        cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', chunk, flags=re.IGNORECASE | re.DOTALL)
        normalized = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
        if len(normalized) < 5:
            continue
        symbol = normalize_symbol(normalized[0])
        if not symbol or symbol in {'SYMBOL', 'TICKER'}:
            continue
        last_price = _parse_float(normalized[2]) if len(normalized) > 2 else None
        if last_price is None:
            continue
        rows.append(
            MarketDataRow(
                symbol=symbol,
                company_name=normalized[1] if len(normalized) > 1 else symbol,
                canonical_entity_id='',
                last_price=last_price,
                price_change=_parse_float(normalized[3]) if len(normalized) > 3 else None,
                percent_change=_parse_float(str(normalized[4]).replace('%', '')) if len(normalized) > 4 else None,
                volume=_parse_int(normalized[5]) if len(normalized) > 5 else None,
                value_traded=_parse_float(normalized[6]) if len(normalized) > 6 else None,
                session_date=now_utc.date().isoformat(),
                market_status='unknown',
                source_name=source_name,
                source_class=MarketSourceClass.priority_1_official_market.value,
                source_url='https://www.boursakuwait.com.kw/en/market-watch',
                fetched_at_utc=now_utc.isoformat(),
                source_trace_id=f'{source_name}:{symbol}:{int(now_utc.timestamp())}',
            )
        )
    return rows


def _parse_yahoo_rows(body: str, now_utc: datetime, source_name: str) -> list[MarketDataRow]:
    payload = json.loads(body)
    records = payload.get('quoteResponse', {}).get('result', [])
    output: list[MarketDataRow] = []
    for rec in records:
        symbol = normalize_symbol(str(rec.get('symbol', '')))
        if not symbol:
            continue
        regular_time = rec.get('regularMarketTime')
        fetched_at = (
            datetime.fromtimestamp(int(regular_time), tz=timezone.utc).isoformat()
            if isinstance(regular_time, (int, float))
            else now_utc.isoformat()
        )
        market_state = str(rec.get('marketState', 'UNKNOWN')).lower()
        output.append(
            MarketDataRow(
                symbol=symbol,
                company_name=str(rec.get('shortName', symbol)),
                canonical_entity_id='',
                last_price=float(rec.get('regularMarketPrice')),
                price_change=_parse_float(rec.get('regularMarketChange')),
                percent_change=_parse_float(rec.get('regularMarketChangePercent')),
                volume=_parse_int(rec.get('regularMarketVolume')),
                value_traded=None,
                session_date=now_utc.date().isoformat(),
                market_status=market_state,
                source_name=source_name,
                source_class=MarketSourceClass.priority_3_secondary_market_data.value,
                source_url='https://query1.finance.yahoo.com/v7/finance/quote',
                fetched_at_utc=fetched_at,
                source_trace_id=f'{source_name}:{symbol}:{int(now_utc.timestamp())}',
            )
        )
    return output


def fetch_market_rows_from_source(
    source: MarketSourceCatalogEntry,
    tradable_universe: list[UniverseRecord],
    now_utc: datetime,
) -> tuple[list[MarketDataRow], MarketSourceStatus]:
    symbols = [f'{u.symbol}.KW' for u in tradable_universe]
    url = source.url
    if source.source_name == 'yahoo_finance_quote':
        url = f"{source.url}?symbols={','.join(symbols)}"

    status_code, body, error = _fetch_raw_url(url=url, timeout_sec=source.timeout_sec)
    if body is None:
        status = MarketSourceStatus(
            source_name=source.source_name,
            source_class=source.source_class.value,
            attempted=True,
            success=False,
            rows_fetched=0,
            error=error or 'empty_response',
            fallback_used=source.fallback_priority > 1,
            notes='network or response failure',
        )
        return [], status

    rows: list[MarketDataRow] = []
    parse_error: str | None = None
    try:
        if source.source_name.startswith('boursa_kuwait'):
            rows = _parse_boursa_rows(body=body, now_utc=now_utc, source_name=source.source_name)
        elif source.source_name == 'yahoo_finance_quote':
            rows = _parse_yahoo_rows(body=body, now_utc=now_utc, source_name=source.source_name)
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        parse_error = str(exc)
        rows = []

    status = MarketSourceStatus(
        source_name=source.source_name,
        source_class=source.source_class.value,
        attempted=True,
        success=len(rows) > 0,
        rows_fetched=len(rows),
        error=parse_error,
        fallback_used=source.fallback_priority > 1,
        notes='ok' if rows else 'empty_or_unparsable_response',
    )
    return rows, status


def build_alias_map(tradable_universe: list[UniverseRecord]) -> dict[str, str]:
    alias_map: dict[str, str] = {}
    for row in tradable_universe:
        alias_map[row.symbol] = row.symbol
        alias_map[normalize_symbol(row.english_name)] = row.symbol
    return alias_map


def normalize_and_map_market_rows(
    rows: list[MarketDataRow],
    tradable_universe: list[UniverseRecord],
) -> tuple[list[MarketDataRow], list[str]]:
    known_symbols = {u.symbol for u in tradable_universe}
    alias_map = build_alias_map(tradable_universe)
    resolved: list[MarketDataRow] = []
    errors: list[str] = []
    for row in rows:
        resolution = resolve_to_canonical_symbol(row.symbol, known_symbols, aliases=alias_map)
        if resolution.status != 'accepted' or resolution.canonical_symbol is None:
            errors.append(f'unresolved_symbol:{row.symbol}:{resolution.reason}')
            continue
        resolved.append(
            MarketDataRow(
                symbol=resolution.canonical_symbol,
                company_name=row.company_name,
                canonical_entity_id=f'KW:{resolution.canonical_symbol}',
                last_price=row.last_price,
                price_change=row.price_change,
                percent_change=row.percent_change,
                volume=row.volume,
                value_traded=row.value_traded,
                session_date=row.session_date,
                market_status=row.market_status,
                source_name=row.source_name,
                source_class=row.source_class,
                source_url=row.source_url,
                fetched_at_utc=row.fetched_at_utc,
                source_trace_id=row.source_trace_id,
            )
        )
    return resolved, errors


def evaluate_market_data_quality(
    rows: list[MarketDataRow],
    source_statuses: list[MarketSourceStatus],
    unresolved_errors: list[str],
    now_utc: datetime,
    max_staleness_hours: int = 36,
) -> MarketDataQualityReport:
    failures: list[str] = []
    limitations: list[str] = []
    if not rows:
        failures.append('empty_source_response')
    if unresolved_errors:
        failures.append('unresolved_canonical_mapping')
        limitations.extend(unresolved_errors)
    seen_symbols: set[str] = set()
    for row in rows:
        if row.symbol in seen_symbols:
            failures.append('duplicate_rows')
            break
        seen_symbols.add(row.symbol)
        if row.last_price <= 0:
            failures.append('impossible_values')
        fetched_at = datetime.fromisoformat(row.fetched_at_utc)
        if now_utc - fetched_at > timedelta(hours=max_staleness_hours):
            failures.append('stale_data')

    primary_ok = any(
        s.success and s.source_class == MarketSourceClass.priority_1_official_market.value for s in source_statuses
    )
    if not primary_ok:
        limitations.append('priority_1_official_source_unavailable_or_unparsable')

    return MarketDataQualityReport(
        run_id=f'market_data_{int(now_utc.timestamp())}',
        rows_total=len(rows),
        unique_symbols=len({r.symbol for r in rows}),
        source_count=len(source_statuses),
        primary_source_ok=primary_ok,
        validation_failures=sorted(set(failures)),
        limitations=limitations,
        ready_for_downstream=(len(failures) == 0 and len(rows) > 0),
    )


def build_market_data_snapshot(
    rows: list[MarketDataRow],
    quality: MarketDataQualityReport,
    source_statuses: list[MarketSourceStatus],
    mode: str,
    now_utc: datetime,
) -> MarketDataSnapshot:
    successful = [s.source_name for s in source_statuses if s.success]
    primary = successful[0] if successful else source_statuses[0].source_name
    metadata = MarketDataIngestionMetadata(
        mode=mode,
        primary_source=primary,
        attempted_sources=[s.source_name for s in source_statuses],
        successful_sources=successful,
        fallback_used=(primary != 'boursa_kuwait_market_watch'),
        limitations=quality.limitations,
    )
    return MarketDataSnapshot(
        snapshot_id=f'kw_market_{now_utc.strftime("%Y%m%dT%H%M%SZ")}',
        as_of_utc=now_utc.isoformat(),
        trading_session_date=now_utc.date().isoformat(),
        rows=rows,
        quality=quality,
        sources=source_statuses,
        metadata=metadata,
    )


def write_market_data_artifacts(root: Path, snapshot: MarketDataSnapshot) -> list[str]:
    runtime_latest = root / 'runtime' / 'latest'
    runtime_quality = root / 'runtime' / 'quality'
    reports = root / 'reports'
    runtime_latest.mkdir(parents=True, exist_ok=True)
    runtime_quality.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)

    snapshot_json = runtime_latest / 'market_data_snapshot.json'
    table_csv = runtime_latest / 'market_data_table.csv'
    quality_json = runtime_quality / 'market_data_quality_report.json'
    source_json = runtime_quality / 'market_source_report.json'
    report_md = reports / 'market_data_summary.md'
    report_snapshot = reports / 'market_data_snapshot_latest.json'
    report_table = reports / 'market_data_table_latest.csv'

    snapshot_json.write_text(json.dumps(asdict(snapshot), indent=2), encoding='utf-8')
    quality_json.write_text(json.dumps(asdict(snapshot.quality), indent=2), encoding='utf-8')
    source_json.write_text(json.dumps([asdict(row) for row in snapshot.sources], indent=2), encoding='utf-8')
    report_snapshot.write_text(snapshot_json.read_text(encoding='utf-8'), encoding='utf-8')

    headers = [
        'symbol',
        'company_name',
        'canonical_entity_id',
        'last_price',
        'price_change',
        'percent_change',
        'volume',
        'value_traded',
        'session_date',
        'market_status',
        'source_name',
        'source_class',
        'source_url',
        'fetched_at_utc',
        'source_trace_id',
    ]
    with io.StringIO() as buf:
        writer = csv.DictWriter(buf, fieldnames=headers)
        writer.writeheader()
        for row in snapshot.rows:
            writer.writerow(asdict(row))
        table_value = buf.getvalue()
    table_csv.write_text(table_value, encoding='utf-8')
    report_table.write_text(table_value, encoding='utf-8')

    report_md.write_text(
        '\n'.join([
            '# Market Data Summary',
            '',
            f"- snapshot_id: `{snapshot.snapshot_id}`",
            f"- as_of_utc: `{snapshot.as_of_utc}`",
            f"- rows_total: `{snapshot.quality.rows_total}`",
            f"- primary_source_ok: `{snapshot.quality.primary_source_ok}`",
            f"- ready_for_downstream: `{snapshot.quality.ready_for_downstream}`",
            f"- successful_sources: `{', '.join(snapshot.metadata.successful_sources) if snapshot.metadata.successful_sources else 'none'}`",
            f"- limitations: `{'; '.join(snapshot.quality.limitations) if snapshot.quality.limitations else 'none'}`",
        ]),
        encoding='utf-8',
    )
    return [
        str(snapshot_json),
        str(table_csv),
        str(quality_json),
        str(source_json),
        str(report_md),
        str(report_snapshot),
        str(report_table),
    ]
