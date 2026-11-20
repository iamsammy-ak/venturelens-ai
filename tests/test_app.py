"""End-to-end UI test: runs the real Streamlit script headlessly (no browser, no model calls)."""

from streamlit.testing.v1 import AppTest

from venturelens.demo import load_samples


def _app() -> AppTest:
    at = AppTest.from_file("../app.py", default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    return at


def test_app_renders_headline_metrics_and_tabs():
    at = _app()
    labels = [m.label for m in at.metric]
    assert any(label.startswith("Score") for label in labels)
    assert "LTV : CAC" in labels
    assert len(at.tabs) == 7


def test_every_sample_and_blank_idea_render():
    at = _app()
    for name in [s["idea"]["name"] for s in load_samples()] + ["Blank idea"]:
        at.selectbox(key="sample_choice").set_value(name).run()
        assert not at.exception, (name, at.exception)
        assert at.text_input(key="idea_name").value == ("" if name == "Blank idea" else name)


def test_changing_an_assumption_updates_the_model():
    at = _app()
    before = next(m.value for m in at.metric if m.label == "LTV : CAC")
    at.number_input(key="cac").set_value(10_000.0).run()
    after = next(m.value for m in at.metric if m.label == "LTV : CAC")
    assert before != after


def test_demo_mode_without_key_explains_setup(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    at = AppTest.from_file("../app.py", default_timeout=60)
    at.secrets["OPENROUTER_API_KEY"] = ""
    at.run()
    assert not at.exception, at.exception
    at.selectbox(key="sample_choice").set_value("GreenFleet").run()
    assert not at.exception, at.exception
    assert any("OPENROUTER_API_KEY" in box.value for box in at.info)
    assert at.button[0].disabled  # Run AI analysis needs a key
