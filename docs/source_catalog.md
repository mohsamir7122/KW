# Source Governance + Evidence Normalization

## Taxonomy
- official_exchange
- regulated_filing
- major_financial_media
- local_press
- secondary_aggregator
- macro_context_only

## Normalized evidence fields
- canonical_entity_id
- symbol
- source_name
- source_type
- evidence_type
- polarity
- confidence
- tradable_impact
- timestamp
- freshness_bucket
- source_reference

## Policy
- context entities are quarantined before scoring.
- governance uses normalized evidence for trust/contribution eligibility.
- ranking never re-computes trust logic.

## Phase 10 market data source classes (explicit priority)
- `priority_1_official_market`: Boursa Kuwait market-watch/public market pages (primary price source of truth).
- `priority_2_exchange_adjacent`: Boursa Kuwait data/research/report pages (official fallback when P1 is unavailable).
- `priority_3_secondary_market_data`: Yahoo Finance / Investing / similar (secondary fallback/cross-check only).
- `priority_4_news_context`: Reuters/CNBC Arabia/Al Jazeera/Kuwait economic press (context only, never price truth).

## Phase 10 feed governance rules
- Always attempt priority 1 official source first.
- Secondary sources never silently override official rows.
- Every market row keeps source traceability (`source_name`, `source_url`, `source_trace_id`, `fetched_at_utc`).
- If data is empty, stale, contradictory, unmapped, or malformed: fail closed and mark `ready_for_downstream=false`.
