from __future__ import annotations

from dataclasses import asdict, dataclass

from .models import CandidateRecord


@dataclass(frozen=True)
class CandidateExplanation:
    symbol: str
    decision: str
    reason: str
    contributing_factors: dict[str, float]
    governance_blocks: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ExclusionExplanation:
    input_value: str
    decision: str
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


def explain_candidate(candidate: CandidateRecord) -> CandidateExplanation:
    return CandidateExplanation(
        symbol=candidate.symbol,
        decision='included',
        reason=candidate.reason,
        contributing_factors={
            'base_signal': candidate.base_signal,
            'trust_score': candidate.trust_score,
            'final_score': candidate.final_score,
        },
        governance_blocks=[],
    )


def explain_exclusion(input_value: str, reason: str) -> ExclusionExplanation:
    return ExclusionExplanation(input_value=input_value, decision='excluded', reason=reason)
