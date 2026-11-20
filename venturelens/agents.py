"""The two AI agents: an analyst that returns a structured assessment, and a memo writer
that turns the assessment plus the computed numbers into an investment memo."""

from __future__ import annotations

import json
from typing import Protocol

from .llm import clean_text
from .schemas import IdeaAssessment, IdeaInput


class SupportsLLM(Protocol):
    def complete_json(self, system: str, user: str, schema: type, **kwargs): ...
    def chat(self, system: str, user: str, **kwargs) -> str: ...


ANALYST_SYSTEM = """You are a seasoned early-stage venture analyst sitting on an investment committee.
Assess business ideas candidly and specifically: avoid generic startup advice.
Only name competitors you are confident exist; when unsure, describe the type of competitor instead.
Scores run from 0 to 10, where 10 is the most favourable for the founder."""

MEMO_SYSTEM = """You write one-page investment memos for an early-stage investment committee.
Use Markdown with exactly these sections: ## Summary, ## Opportunity, ## Business model and unit economics,
## Financial outlook, ## Key risks, ## Recommendation.
Use only the figures provided and write them exactly as given; never invent numbers or sources.
Be direct and balanced. 350-500 words. Return the memo only, without a title line."""


def assess_idea(llm: SupportsLLM, idea: IdeaInput) -> IdeaAssessment:
    user = f"""Business idea to assess
Name: {idea.name}
Description: {idea.description}
Target customer: {idea.target_customer or "not specified"}
Geography: {idea.geography or "not specified"}
Business model: {idea.business_model}

Score each dimension from 0 to 10 (10 = most favourable):
- problem_urgency: how painful and frequent the problem is for the target customer
- competitive_position: how favourable the competitive landscape is (10 = little credible competition)
- defensibility: potential for moats such as network effects, proprietary data, switching costs, brand or IP
- execution_feasibility: how achievable this is for a small team with seed funding (10 = very feasible)

Also give: 3-6 competitors or substitutes; a SWOT with 3-4 points per quadrant; 4-6 key risks with
severity (low/medium/high) and a mitigation each; 5 questions an investor would ask; and 3-5 cheap
experiments that would validate demand within a month."""
    return llm.complete_json(ANALYST_SYSTEM, user, IdeaAssessment)


def write_memo(llm: SupportsLLM, idea: IdeaInput, assessment: IdeaAssessment, facts: dict) -> str:
    user = (
        "Idea:\n"
        + idea.model_dump_json(indent=2)
        + "\n\nAnalyst assessment:\n"
        + assessment.model_dump_json(indent=2)
        + "\n\nComputed figures (authoritative, use exactly as written):\n"
        + json.dumps(facts, indent=2, ensure_ascii=False)
    )
    return clean_text(llm.chat(MEMO_SYSTEM, user, temperature=0.4, max_tokens=1800))
