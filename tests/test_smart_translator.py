from types import SimpleNamespace

from backend.app.smart_translator import (
    make_gemini_semantic_tags,
    restore_gemini_semantic_tags,
    translate_with_gemini,
)
from backend.app.terminology import DetectedTerm, restore_technical_terms


def detected(
    term: str, action: str, preferred_khmer: str | None = None
) -> DetectedTerm:
    return DetectedTerm(
        term=term,
        action=action,
        preferred_khmer=preferred_khmer,
    )


def test_keep_tag_generation() -> None:
    tagged, tag_map, metadata = make_gemini_semantic_tags(
        "Use __VITOU_TERM_0__.",
        {"__VITOU_TERM_0__": "Database"},
        [detected("Database", "KEEP")],
    )

    expected = '<vl-keep id="0">Database</vl-keep>'
    assert tagged == f"Use {expected}."
    assert tag_map == {expected: "__VITOU_TERM_0__"}
    assert metadata[0]["action"] == "KEEP"


def test_preferred_tag_generation() -> None:
    tagged, _, metadata = make_gemini_semantic_tags(
        "Open __VITOU_TERM_0__.",
        {"__VITOU_TERM_0__": "កម្មវិធីរុករកវេប"},
        [detected("web browser", "PREFERRED", "កម្មវិធីរុករកវេប")],
    )

    assert tagged == (
        'Open <vl-preferred id="0">web browser</vl-preferred>.'
    )
    assert metadata[0]["restored_value"] == "កម្មវិធីរុករកវេប"


def test_no_detected_terms() -> None:
    tagged, tag_map, metadata = make_gemini_semantic_tags(
        "Translate this sentence.", {}, []
    )

    assert tagged == "Translate this sentence."
    assert tag_map == {}
    assert metadata == []


def test_repeated_occurrence_gets_unique_tags() -> None:
    tagged, tag_map, metadata = make_gemini_semantic_tags(
        "__VITOU_TERM_0__ calls __VITOU_TERM_1__.",
        {
            "__VITOU_TERM_0__": "API",
            "__VITOU_TERM_1__": "API",
        },
        [detected("API", "KEEP"), detected("API", "KEEP")],
    )

    assert '<vl-keep id="0">API</vl-keep>' in tagged
    assert '<vl-keep id="1">API</vl-keep>' in tagged
    assert len(tag_map) == 2
    assert [item["id"] for item in metadata] == [0, 1]


def test_successful_keep_and_preferred_restoration() -> None:
    placeholders = {
        "__VITOU_TERM_0__": "Database",
        "__VITOU_TERM_1__": "កម្មវិធីរុករកវេប",
    }
    tagged, tag_map, _ = make_gemini_semantic_tags(
        "__VITOU_TERM_0__ works in __VITOU_TERM_1__.",
        placeholders,
        [
            detected("Database", "KEEP"),
            detected("web browser", "PREFERRED", "កម្មវិធីរុករកវេប"),
        ],
    )

    raw_output = tagged.replace("works in", "ដំណើរការនៅក្នុង")
    placeholders_restored = restore_gemini_semantic_tags(raw_output, tag_map)
    final_output = restore_technical_terms(placeholders_restored, placeholders)

    assert final_output == "Database ដំណើរការនៅក្នុង កម្មវិធីរុករកវេប."


def test_translate_flow_uses_mock_client_without_real_api_call(monkeypatch) -> None:
    class FakeModels:
        def __init__(self) -> None:
            self.calls = 0

        def generate_content(self, **kwargs):
            self.calls += 1
            return SimpleNamespace(text="នេះជាលទ្ធផលបកប្រែសាកល្បង។")

    fake_models = FakeModels()
    fake_client = SimpleNamespace(models=fake_models)
    monkeypatch.setattr(
        "backend.app.smart_translator.protect_technical_terms",
        lambda text, terms: (text, {}, []),
    )

    result = translate_with_gemini(
        fake_client,
        "This is a deterministic translation test.",
        "testing",
        [],
        sleep=lambda _: None,
    )

    assert fake_models.calls == 1
    assert result["raw_output"] == "នេះជាលទ្ធផលបកប្រែសាកល្បង។"
    assert result["validation_passed"] is True
