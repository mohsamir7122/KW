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
