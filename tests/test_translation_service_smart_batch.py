from typing import Any

import pytest

from backend.app.translation_service import (
    SmartModeUnavailableError,
    SmartTranslationError,
    SmartTranslationRejectedError,
    TranslationOrchestrator,
)


def valid_batch_result(
    texts: list[str],
) -> dict[str, Any]:
    return {
        "results": [
            {
                "item_index": index,
                "output": (
                    f"ការបកប្រែសាកល្បងទី{index}។"
                ),
                "validation_passed": True,
                "detected_terms": [
                    {
                        "term": "API",
                        "action": "KEEP",
                        "preferred_khmer": None,
                    }
                ],
            }
            for index, _text in enumerate(texts)
        ],
        "validation_passed": True,
    }


def test_smart_many_uses_batch_translator_once():
    calls: list[
        tuple[
            object,
            list[str],
            str,
        ]
    ] = []

    fake_client = object()

    def translate_many(
        client: object,
        texts: list[str],
        domain: str,
        _terms: list[Any],
    ) -> dict[str, Any]:
        calls.append(
            (
                client,
                list(texts),
                domain,
            )
        )

        return valid_batch_result(texts)

    service = TranslationOrchestrator(
        api_key_provider=lambda: "test-key",
        smart_client_factory=(
            lambda _api_key: fake_client
        ),
        smart_translate_many=translate_many,
    )

    texts = [
        "The API receives a request.",
        "The server returns a response.",
    ]

    results = service.translate_smart_many(
        texts,
        "Web Development",
    )

    assert calls == [
        (
            fake_client,
            texts,
            "Web Development",
        )
    ]

    assert len(results) == 2

    assert results[0]["mode"] == "smart"

    assert (
        results[0]["validation_passed"]
        is True
    )

    assert (
        results[0]["translation"]
        == "ការបកប្រែសាកល្បងទី0។"
    )

    assert results[0]["detected_terms"] == [
        "API"
    ]

    assert set(results[0]) == {
        "original_text",
        "processed_text",
        "detected_terms",
        "term_policies",
        "status",
        "mode",
        "engine",
        "validation_passed",
        "translation",
    }


def test_smart_many_requires_api_key():
    called = False

    def translate_many(*_args, **_kwargs):
        nonlocal called
        called = True

        return {}

    service = TranslationOrchestrator(
        api_key_provider=lambda: None,
        smart_translate_many=translate_many,
    )

    with pytest.raises(
        SmartModeUnavailableError
    ):
        service.translate_smart_many(
            [
                "Translate this.",
            ],
            "Computer Science",
        )

    assert called is False


def test_smart_many_rejects_failed_batch_validation():
    def translate_many(*_args, **_kwargs):
        return {
            "results": [
                {
                    "item_index": 0,
                    "output": None,
                    "validation_passed": False,
                    "rejected_output": (
                        "sensitive rejected output"
                    ),
                }
            ],
            "validation_passed": False,
            "validation_issues": [
                "item_0:missing_tags"
            ],
            "raw_outputs": [
                "sensitive raw output"
            ],
        }

    service = TranslationOrchestrator(
        api_key_provider=lambda: "test-key",
        smart_client_factory=lambda _: object(),
        smart_translate_many=translate_many,
    )

    with pytest.raises(
        SmartTranslationRejectedError
    ):
        service.translate_smart_many(
            [
                "Translate this.",
            ],
            "Computer Science",
        )


def test_smart_many_rejects_changed_item_order():
    def translate_many(*_args, **_kwargs):
        return {
            "results": [
                {
                    "item_index": 1,
                    "output": "ការបកប្រែទីមួយ។",
                    "validation_passed": True,
                    "detected_terms": [],
                },
                {
                    "item_index": 0,
                    "output": "ការបកប្រែទីពីរ។",
                    "validation_passed": True,
                    "detected_terms": [],
                },
            ],
            "validation_passed": True,
        }

    service = TranslationOrchestrator(
        api_key_provider=lambda: "test-key",
        smart_client_factory=lambda _: object(),
        smart_translate_many=translate_many,
    )

    with pytest.raises(
        SmartTranslationRejectedError
    ):
        service.translate_smart_many(
            [
                "First text.",
                "Second text.",
            ],
            "Computer Science",
        )


def test_smart_many_provider_failure_does_not_fallback():
    class NoFallbackBasicTranslator:
        def translate_many_with_details(
            self,
            _items,
        ):
            raise AssertionError(
                "Basic fallback must not run."
            )

    def fail_translation(
        *_args,
        **_kwargs,
    ):
        raise RuntimeError(
            "sensitive provider failure"
        )

    service = TranslationOrchestrator(
        basic_translator=(
            NoFallbackBasicTranslator()
        ),
        api_key_provider=lambda: "test-key",
        smart_client_factory=lambda _: object(),
        smart_translate_many=fail_translation,
    )

    with pytest.raises(
        SmartTranslationError
    ):
        service.translate_smart_many(
            [
                "Translate this.",
            ],
            "Computer Science",
        )
