import re
from difflib import SequenceMatcher
from typing import Any


GENERIC_VL_TAG_PATTERN = re.compile(r"</?vl-[^>]+>", flags=re.IGNORECASE)
MALFORMED_VL_TAG_PATTERN = re.compile(r"<\s*/?\s*vl-", flags=re.IGNORECASE)
LEGACY_MARKER_PATTERN = re.compile(r"\bVITOUTERM\d+[A-Z]?\b", flags=re.IGNORECASE)
KHMER_CHARACTER_PATTERN = re.compile(r"[\u1780-\u17FF]")
LATIN_CHARACTER_PATTERN = re.compile(r"[A-Za-z]")


def validate_raw_tags(raw_output: str, tag_map: dict[str, str]) -> dict[str, Any]:
    missing_tags: list[str] = []
    duplicate_tags: list[str] = []
    remaining_output = raw_output

    for expected_tag in tag_map:
        occurrence_count = raw_output.count(expected_tag)
        if occurrence_count == 0:
            missing_tags.append(expected_tag)
        elif occurrence_count > 1:
            duplicate_tags.append(expected_tag)
        remaining_output = remaining_output.replace(expected_tag, "")

    unexpected_tags = sorted(set(GENERIC_VL_TAG_PATTERN.findall(remaining_output)))
    legacy_markers = sorted(set(LEGACY_MARKER_PATTERN.findall(raw_output)))
    malformed_tag_text = MALFORMED_VL_TAG_PATTERN.search(remaining_output) is not None

    issues: list[str] = []
    if missing_tags:
        issues.append("missing_tags")
    if duplicate_tags:
        issues.append("duplicate_tags")
    if unexpected_tags:
        issues.append("unexpected_tags")
    if legacy_markers:
        issues.append("legacy_or_invented_markers")
    if malformed_tag_text:
        issues.append("malformed_tag_text")

    return {
        "passed": not issues,
        "issues": issues,
        "expected_tag_count": len(tag_map),
        "missing_tags": missing_tags,
        "duplicate_tags": duplicate_tags,
        "unexpected_tags": unexpected_tags,
        "legacy_markers": legacy_markers,
        "malformed_tag_text": malformed_tag_text,
    }


def normalize_for_comparison(text: str) -> str:
    return " ".join(text.split()).strip().lower()


def calculate_length_ratio(source_text: str, output_text: str) -> float:
    normalized_source = normalize_for_comparison(source_text)
    normalized_output = normalize_for_comparison(output_text)
    return len(normalized_output) / max(len(normalized_source), 1)


def detect_unchanged_english_output(
    source_text: str, output_text: str
) -> tuple[bool, float]:
    normalized_source = normalize_for_comparison(source_text)
    normalized_output = normalize_for_comparison(output_text)
    similarity = SequenceMatcher(None, normalized_source, normalized_output).ratio()
    khmer_count = len(KHMER_CHARACTER_PATTERN.findall(output_text))
    latin_count = len(LATIN_CHARACTER_PATTERN.findall(output_text))
    exactly_unchanged = normalized_source == normalized_output
    mostly_unchanged_english = (
        similarity >= 0.80
        and khmer_count < 5
        and latin_count > khmer_count
    )
    return exactly_unchanged or mostly_unchanged_english, round(similarity, 3)


def detect_repeated_word_degeneration(text: str) -> bool:
    spaced_repetition = re.search(
        (
            r"(?iu)([A-Za-z\u1780-\u17FF]"
            r"[A-Za-z0-9_\-+#.\u1780-\u17FF]{1,30})"
            r"(?:[\s,;:។]+\1){4,}"
        ),
        text,
    )
    if spaced_repetition:
        return True

    contiguous_repetition = re.search(
        r"(?iu)([A-Za-z\u1780-\u17FF]{2,20})(?:\1){4,}",
        text,
    )
    return contiguous_repetition is not None


def validate_final_output(source_text: str, output_text: str) -> dict[str, Any]:
    issues: list[str] = []
    normalized_output = normalize_for_comparison(output_text)
    empty_result = not normalized_output
    length_ratio = calculate_length_ratio(source_text, output_text)
    output_too_short = length_ratio < 0.25
    output_too_long = length_ratio > 4.0
    unchanged_english_output, similarity = detect_unchanged_english_output(
        source_text, output_text
    )
    repeated_word_degeneration = detect_repeated_word_degeneration(output_text)
    leftover_tags = sorted(set(GENERIC_VL_TAG_PATTERN.findall(output_text)))
    leftover_legacy_markers = sorted(set(LEGACY_MARKER_PATTERN.findall(output_text)))

    if empty_result:
        issues.append("empty_result")
    if output_too_short:
        issues.append("output_too_short")
    if output_too_long:
        issues.append("output_too_long")
    if unchanged_english_output:
        issues.append("unchanged_english_output")
    if repeated_word_degeneration:
        issues.append("repeated_word_degeneration")
    if leftover_tags:
        issues.append("leftover_tags")
    if leftover_legacy_markers:
        issues.append("leftover_legacy_markers")

    return {
        "passed": not issues,
        "issues": issues,
        "empty_result": empty_result,
        "length_ratio": round(length_ratio, 3),
        "output_too_short": output_too_short,
        "output_too_long": output_too_long,
        "source_similarity": similarity,
        "unchanged_english_output": unchanged_english_output,
        "repeated_word_degeneration": repeated_word_degeneration,
        "leftover_tags": leftover_tags,
        "leftover_legacy_markers": leftover_legacy_markers,
    }
