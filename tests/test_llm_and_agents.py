"""LLM parsing and agent tests. No network: a fake client stands in for OpenRouter."""

import json

import pytest

from venturelens.agents import assess_idea, write_memo
from venturelens.config import Settings
from venturelens.finance import Assumptions, MarketInputs
from venturelens.llm import LLMClient, LLMError, clean_text, extract_json
from venturelens.pipeline import compute, fingerprint, idea_fingerprint, run_ai
from venturelens.schemas import IdeaAssessment, IdeaInput

ASSESSMENT = {
    "one_liner": "Verified student housing for international students.",
    "target_customer": "Small landlords",
    "value_proposition": "Pre-screened tenants",
    "problem_urgency": {"score": "8/10", "rationale": "Acute shortage"},
    "competitive_position": {"score": 6, "rationale": "Fragmented"},
    "defensibility": {"score": 14, "rationale": "Clamped to 10"},
    "execution_feasibility": {"score": "seven", "rationale": "Unparseable falls back to 5"},
    "competitors": [{"name": "HousingAnywhere", "kind": "Direct competitor", "note": "Pan-European"}],
    "swot": {"strengths": [{"point": "Local focus"}], "weaknesses": "Single city", "opportunities": [], "threats": []},
    "risks": [{"risk": "Chicken-and-egg", "severity": "HIGH", "mitigation": "Seed supply"}],
    "investor_questions": ["How do you acquire landlords?"],
    "validation_experiments": ["Landing page"],
}


class FakeLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.last_model = "fake/model"

    def chat(self, system, user, **kwargs):
        return self.replies.pop(0)

    def complete_json(self, system, user, schema, **kwargs):
        return schema.model_validate(extract_json(self.chat(system, user)))


IDEA = IdeaInput(name="StudyNest", description="Student housing marketplace")


def test_extract_json_variants():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('```json\n{"a": 2}\n```') == {"a": 2}
    assert extract_json('<think>hmm {"no": 1}</think>Sure! {"a": 3} hope that helps') == {"a": 3}
    with pytest.raises(ValueError):
        extract_json("no json here")
    with pytest.raises(ValueError):
        extract_json("[1, 2]")


def test_clean_text_strips_reasoning_and_fence():
    assert clean_text("<think>plan</think>\n## Summary\nok") == "## Summary\nok"
    assert clean_text("```markdown\n## Summary\n```") == "## Summary"


def test_schema_coercion():
    a = IdeaAssessment.model_validate(ASSESSMENT)
    assert a.problem_urgency.score == 8
    assert a.defensibility.score == 10
    assert a.execution_feasibility.score == 5
    assert a.competitors[0].kind == "direct"
    assert a.risks[0].severity == "high"
    assert a.swot.strengths == ["Local focus"]
    assert a.swot.weaknesses == ["Single city"]


def test_assess_and_memo_with_fake_llm():
    fake = FakeLLM([json.dumps(ASSESSMENT), "<think>x</think>## Summary\nGood."])
    assessment = assess_idea(fake, IDEA)
    assert assessment.one_liner.startswith("Verified")
    assert write_memo(fake, IDEA, assessment, {"LTV": "€1k"}) == "## Summary\nGood."


def test_run_ai_returns_serialisable_analysis():
    a, m = Assumptions(), MarketInputs()
    fake = FakeLLM([json.dumps(ASSESSMENT), "## Summary\nMemo"])
    steps = []
    result = run_ai(fake, IDEA, a, m, compute(a, m), on_step=steps.append)
    json.dumps(result)
    assert result["fingerprint"] == fingerprint(IDEA, a, m)
    assert result["idea_fingerprint"] == idea_fingerprint(IDEA)
    assert len(steps) == 2


def test_fingerprint_ignores_float_noise_but_not_real_changes():
    a = Assumptions(new_customer_growth=0.07)
    noisy = Assumptions(new_customer_growth=7.000000000000001 / 100)
    assert fingerprint(IDEA, a, MarketInputs()) == fingerprint(IDEA, noisy, MarketInputs())
    assert fingerprint(IDEA, a, MarketInputs()) != fingerprint(IDEA, Assumptions(cac=1), MarketInputs())


def test_client_requires_key():
    with pytest.raises(LLMError):
        LLMClient(Settings(api_key=None))


def test_complete_json_repairs_once(tmp_path, monkeypatch):
    client = LLMClient(Settings(api_key="test", models=("fake/model",)), cache_dir=tmp_path)
    replies = iter(["not json at all", json.dumps({"one_liner": "x", **{k: ASSESSMENT[k] for k in (
        "problem_urgency", "competitive_position", "defensibility", "execution_feasibility")}})])
    monkeypatch.setattr(client, "_call_with_fallback", lambda *args, **kw: (next(replies), "fake/model"))
    result = client.complete_json("sys", "user", IdeaAssessment)
    assert result.one_liner == "x"
    # only the valid repaired answer stays cached
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_chat_uses_cache(tmp_path, monkeypatch):
    client = LLMClient(Settings(api_key="test", models=("fake/model",)), cache_dir=tmp_path)
    calls = []

    def fake_call(*args, **kw):
        calls.append(1)
        return "hello", "fake/model"

    monkeypatch.setattr(client, "_call_with_fallback", fake_call)
    assert client.chat("s", "u") == "hello"
    assert client.chat("s", "u") == "hello"
    assert len(calls) == 1
