from venturelens.demo import ANALYSES_DIR, load_samples, load_saved_analysis, sample_inputs
from venturelens.pipeline import compute, fingerprint
from venturelens.report import build_report
from venturelens.schemas import IdeaAssessment
from venturelens.scoring import build_scorecard

BUSINESS_MODELS = {
    "Subscription (SaaS)",
    "Marketplace (take rate)",
    "E-commerce / D2C",
    "Usage-based",
    "Services / agency",
    "Hardware + subscription",
}


def test_samples_are_valid():
    samples = load_samples()
    assert len(samples) >= 3
    for sample in samples:
        idea, a, m = sample_inputs(sample)
        assert idea.business_model in BUSINESS_MODELS
        assert 0 < a.gross_margin <= 1 and 0 <= a.monthly_churn < 1
        assert 0 < m.serviceable_share <= 1 and 0 < m.obtainable_share <= 1


def test_saved_analyses_match_samples_and_parse():
    fingerprints = {fingerprint(*sample_inputs(s)) for s in load_samples()}
    for path in ANALYSES_DIR.glob("*.json"):
        assert path.stem in fingerprints, f"{path.name} does not belong to any sample (stale fixture?)"
        IdeaAssessment.model_validate(load_saved_analysis(path.stem)["assessment"])


def test_report_without_ai_has_all_figures():
    idea, a, m = sample_inputs(load_samples()[0])
    c = compute(a, m)
    card = build_scorecard(c.market, c.unit, c.summary, None, a.months)
    report = build_report(idea, a, m, c, card, None, None, None)
    assert idea.name in report
    for heading in ("Key figures", "Assumptions", "LTV : CAC", "TAM / SAM / SOM"):
        assert heading in report
    assert "partial" in report
