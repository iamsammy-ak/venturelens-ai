"""Pydantic models for the idea input and the AI analyst's structured assessment.

Free models do not always follow a schema exactly, so validators coerce common variations
("8/10", "High", objects where strings were expected) instead of rejecting the reply.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def _as_text(item: Any) -> str:
    if isinstance(item, dict):
        return " — ".join(str(v) for v in item.values() if v not in (None, ""))
    return str(item).strip()


def _as_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        value = [value]
    return [text for text in (_as_text(v) for v in value) if text]


class IdeaInput(BaseModel):
    name: str
    description: str
    target_customer: str = ""
    geography: str = ""
    business_model: str = "Subscription (SaaS)"


class DimensionScore(BaseModel):
    score: float = Field(5.0, description="0 = very unfavourable for the founder, 10 = very favourable")
    rationale: str = Field("", description="One or two sentences explaining the score")

    @field_validator("score", mode="before")
    @classmethod
    def _parse_score(cls, value: Any) -> float:
        if isinstance(value, str):
            match = _NUMBER.search(value)
            value = match.group(0) if match else 5.0
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = 5.0
        return max(0.0, min(10.0, number))


class Competitor(BaseModel):
    name: str
    kind: str = Field("direct", description="direct, indirect or substitute")
    note: str = Field("", description="How it competes and where the idea differs")

    @field_validator("kind", mode="before")
    @classmethod
    def _kind(cls, value: Any) -> str:
        text = str(value or "direct").lower()
        for kind in ("direct", "indirect", "substitute"):
            if kind in text:
                return kind
        return "direct"


class Risk(BaseModel):
    risk: str
    severity: str = Field("medium", description="low, medium or high")
    mitigation: str = ""

    @field_validator("severity", mode="before")
    @classmethod
    def _severity(cls, value: Any) -> str:
        text = str(value or "medium").lower()
        for level in ("high", "medium", "low"):
            if level in text:
                return level
        return "medium"


class Swot(BaseModel):
    strengths: list[str] = []
    weaknesses: list[str] = []
    opportunities: list[str] = []
    threats: list[str] = []

    @field_validator("strengths", "weaknesses", "opportunities", "threats", mode="before")
    @classmethod
    def coerce_text_lists(cls, value: Any) -> list[str]:
        return _as_text_list(value)


class IdeaAssessment(BaseModel):
    one_liner: str = Field(description="The idea in one sharp sentence")
    target_customer: str = ""
    value_proposition: str = ""
    problem_urgency: DimensionScore
    competitive_position: DimensionScore
    defensibility: DimensionScore
    execution_feasibility: DimensionScore
    competitors: list[Competitor] = []
    swot: Swot = Swot()
    risks: list[Risk] = []
    investor_questions: list[str] = []
    validation_experiments: list[str] = []

    @field_validator("investor_questions", "validation_experiments", mode="before")
    @classmethod
    def coerce_text_lists(cls, value: Any) -> list[str]:
        return _as_text_list(value)
