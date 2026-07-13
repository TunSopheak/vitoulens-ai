import json
from types import SimpleNamespace

from backend.app.smart_translator import (
    chunk_smart_texts,
    translate_many_with_gemini,
)


class FakeBatchModels:
    def __init__(
        self,
        responses: list[dict],
    ) -> None:
        self.responses = list(responses)
        self.calls = 0

    def generate_content(self, **_kwargs):
        response = self.responses[self.calls]
        self.calls += 1

        return SimpleNamespace(
            text=json.dumps(
                response,
                ensure_ascii=False,
            )
        )


def make_batch_client(
    responses: list[dict],
):
    models = FakeBatchModels(responses)

    return (
        SimpleNamespace(models=models),
        models,
    )


def khmer_translation() -> str:
    return "នេះជាលទ្ធផលបកប្រែសាកល្បង។"


def test_smart_chunking_respects_item_and_character_limits():
    item_chunks = chunk_smart_texts(
        [
            "Short text."
            for _ in range(9)
        ],
        max_items=8,
        max_characters=6000,
    )

    assert [
        len(chunk)
        for chunk in item_chunks
    ] == [
        8,
        1,
    ]

    character_chunks = chunk_smart_texts(
        [
            "a" * 4000,
            "b" * 3000,
        ],
        max_items=8,
        max_characters=6000,
    )

    assert [
        len(chunk)
        for chunk in character_chunks
    ] == [
        1,
        1,
    ]


def test_smart_batch_uses_three_calls_for_seventeen_items():
    responses = []

    for start, end in (
        (0, 8),
        (8, 16),
        (16, 17),
    ):
        responses.append(
            {
                "items": [
                    {
                        "id": str(index),
                        "translation": (
                            khmer_translation()
                        ),
                    }
                    for index in range(
                        start,
                        end,
                    )
                ]
            }
        )

    client, models = make_batch_client(
        responses
    )

    result = translate_many_with_gemini(
        client,
        [
            "Translate this sentence."
            for _ in range(17)
        ],
        "testing",
        [],
        sleep=lambda _seconds: None,
    )

    assert models.calls == 3
    assert result["chunk_count"] == 3
    assert result["processed_chunk_count"] == 3
    assert result["validation_passed"] is True
    assert len(result["results"]) == 17

    assert [
        item["item_index"]
        for item in result["results"]
    ] == list(range(17))


def test_smart_batch_validates_items_independently():
    client, _models = make_batch_client(
        [
            {
                "items": [
                    {
                        "id": "0",
                        "translation": (
                            khmer_translation()
                        ),
                    },
                    {
                        "id": "1",
                        "translation": (
                            "Translate this sentence."
                        ),
                    },
                ]
            }
        ]
    )

    result = translate_many_with_gemini(
        client,
        [
            "Translate this sentence.",
            "Translate this sentence.",
        ],
        "testing",
        [],
        sleep=lambda _seconds: None,
    )

    assert result["validation_passed"] is False

    assert (
        result["results"][0]["validation_passed"]
        is True
    )

    assert (
        result["results"][1]["validation_passed"]
        is False
    )

    assert (
        "unchanged_english_output"
        in result["results"][1][
            "validation_issues"
        ]
    )

    assert (
        "item_1:unchanged_english_output"
        in result["validation_issues"]
    )


def test_smart_batch_rejects_changed_item_order():
    client, _models = make_batch_client(
        [
            {
                "items": [
                    {
                        "id": "1",
                        "translation": (
                            khmer_translation()
                        ),
                    },
                    {
                        "id": "0",
                        "translation": (
                            khmer_translation()
                        ),
                    },
                ]
            }
        ]
    )

    result = translate_many_with_gemini(
        client,
        [
            "Translate this sentence.",
            "Translate this sentence.",
        ],
        "testing",
        [],
        sleep=lambda _seconds: None,
    )

    assert result["validation_passed"] is False
    assert result["results"] == []

    assert result["validation_issues"] == [
        "chunk_0:"
        "batch_item_ids_or_order_mismatch"
    ]
