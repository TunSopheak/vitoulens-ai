import pytest

from backend.app.translation_validation import (
    detect_repeated_word_degeneration,
    validate_final_output,
    validate_raw_tags,
)


EXPECTED_TAG = '<vl-keep id="0">database</vl-keep>'
TAG_MAP = {EXPECTED_TAG: "__VITOU_TERM_0__"}


def test_missing_expected_tag() -> None:
    result = validate_raw_tags("គ្មានស្លាក។", TAG_MAP)
    assert "missing_tags" in result["issues"]
    assert result["missing_tags"] == [EXPECTED_TAG]


def test_duplicated_expected_tag() -> None:
    result = validate_raw_tags(f"{EXPECTED_TAG} {EXPECTED_TAG}", TAG_MAP)
    assert "duplicate_tags" in result["issues"]
    assert result["duplicate_tags"] == [EXPECTED_TAG]


def test_unexpected_semantic_tag() -> None:
    unexpected = '<vl-preferred id="9">browser</vl-preferred>'
    result = validate_raw_tags(f"{EXPECTED_TAG} {unexpected}", TAG_MAP)
    assert "unexpected_tags" in result["issues"]
    assert result["unexpected_tags"]


def test_malformed_semantic_tag() -> None:
    malformed = '<vl-keep id="0">database</vl-keep'
    result = validate_raw_tags(malformed, TAG_MAP)
    assert "malformed_tag_text" in result["issues"]


def test_whitespace_malformed_semantic_tag_without_expected_tags() -> None:
    malformed = '< vl-keep id="0">database</ vl-keep>'
    result = validate_raw_tags(malformed, {})
    assert "malformed_tag_text" in result["issues"]


def test_invented_vitouterm_marker() -> None:
    result = validate_raw_tags(f"{EXPECTED_TAG} VITOUTERM42A", TAG_MAP)
    assert "legacy_or_invented_markers" in result["issues"]
    assert result["legacy_markers"] == ["VITOUTERM42A"]


def test_leftover_tag_after_restoration() -> None:
    result = validate_final_output(
        "The database stores records.",
        f"មូលដ្ឋានទិន្នន័យ {EXPECTED_TAG} រក្សាទុកទិន្នន័យ។",
    )
    assert "leftover_tags" in result["issues"]


def test_unchanged_english_output() -> None:
    source = "The browser sends a request to the server."
    result = validate_final_output(source, source)
    assert "unchanged_english_output" in result["issues"]


def test_empty_output() -> None:
    result = validate_final_output("Translate this sentence.", "   ")
    assert "empty_result" in result["issues"]


def test_output_too_short() -> None:
    source = "This deliberately long source sentence contains enough text for a ratio check."
    result = validate_final_output(source, "ខ្លី")
    assert "output_too_short" in result["issues"]


def test_output_too_long() -> None:
    result = validate_final_output("Short source.", "អត្ថបទវែង " * 30)
    assert "output_too_long" in result["issues"]


@pytest.mark.parametrize(
    "output",
    [
        "ទិន្នន័យ ទិន្នន័យ ទិន្នន័យ ទិន្នន័យ ទិន្នន័យ",
        "testingtestingtestingtestingtesting",
    ],
)
def test_repeated_word_degeneration(output: str) -> None:
    assert detect_repeated_word_degeneration(output) is True
    result = validate_final_output("A source sentence for testing.", output)
    assert "repeated_word_degeneration" in result["issues"]
