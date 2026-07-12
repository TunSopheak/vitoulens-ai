from pathlib import Path

import pytest

from backend.app.translation_service import (
    TranslationOrchestrator,
)
from backend.app.translator import (
    TranslationError,
    TranslationResult,
)


class RecordingBatchTranslator:
    def __init__(self) -> None:
        self.batch_calls: list[
            list[tuple[str, tuple[str, ...]]]
        ] = []

    def translate_many_with_details(
        self,
        items,
    ):
        normalized = [
            (
                text,
                tuple(placeholders),
            )
            for text, placeholders in items
        ]

        self.batch_calls.append(
            normalized
        )

        return [
            TranslationResult(
                text=text,
                sentence_count=1,
                fallback_used=False,
            )
            for text, _placeholders in normalized
        ]


class MismatchedBatchTranslator(
    RecordingBatchTranslator
):
    def translate_many_with_details(
        self,
        items,
    ):
        normalized = [
            (
                text,
                tuple(placeholders),
            )
            for text, placeholders in items
        ]

        self.batch_calls.append(
            normalized
        )

        return []


def test_basic_many_uses_one_translator_batch_call():
    translator = RecordingBatchTranslator()

    service = TranslationOrchestrator(
        basic_translator=translator,
    )

    results = service.translate_basic_many(
        [
            "The Browser sends an HTTP Request.",
            "Git and GitHub are development tools.",
        ]
    )

    assert len(translator.batch_calls) == 1
    assert len(translator.batch_calls[0]) == 2

    assert len(results) == 2

    assert (
        "កម្មវិធីរុករកវេប"
        in results[0]["processed_text"]
    )

    assert (
        "HTTP"
        in results[0]["processed_text"]
    )

    assert (
        "GitHub"
        in results[1]["processed_text"]
    )


def test_basic_single_translation_uses_batch_path():
    translator = RecordingBatchTranslator()

    service = TranslationOrchestrator(
        basic_translator=translator,
    )

    result = service.translate_basic(
        "The API returns a Response."
    )

    assert len(translator.batch_calls) == 1
    assert len(translator.batch_calls[0]) == 1

    assert (
        result["original_text"]
        == "The API returns a Response."
    )

    assert "API" in result["processed_text"]


def test_basic_many_rejects_mismatched_item_count():
    translator = MismatchedBatchTranslator()

    service = TranslationOrchestrator(
        basic_translator=translator,
    )

    with pytest.raises(
        TranslationError,
        match="unexpected item count",
    ):
        service.translate_basic_many(
            [
                "API request.",
            ]
        )
