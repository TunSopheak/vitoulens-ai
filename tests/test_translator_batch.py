from pathlib import Path

from backend.app.translator import (
    NLLBTranslatorService,
)


class RecordingTranslator(
    NLLBTranslatorService
):
    def __init__(self) -> None:
        super().__init__(
            model_path=Path(
                "unused-test-model"
            )
        )

        self.batch_calls: list[
            list[str]
        ] = []

        self.next_outputs: list[str] = []

    def _translate_batch(
        self,
        sentences: list[str],
    ) -> list[str]:
        self.batch_calls.append(
            list(sentences)
        )

        if self.next_outputs:
            outputs = self.next_outputs
            self.next_outputs = []

            return outputs

        return [
            f"Translated {sentence}"
            for sentence in sentences
        ]


def test_multi_text_translation_uses_one_batch_call():
    service = RecordingTranslator()

    results = service.translate_many_with_details(
        [
            (
                "First sentence. Second sentence.",
                (),
            ),
            (
                "Third sentence.",
                (),
            ),
        ]
    )

    assert len(service.batch_calls) == 1

    assert service.batch_calls[0] == [
        "First sentence.",
        "Second sentence.",
        "Third sentence.",
    ]

    assert len(results) == 2
    assert results[0].sentence_count == 2
    assert results[1].sentence_count == 1


def test_marker_failure_is_isolated_to_one_item():
    service = RecordingTranslator()

    service.next_outputs = [
        "Marker was lost.",
        "Translated plain sentence.",
    ]

    results = service.translate_many_with_details(
        [
            (
                "__VITOU_TERM_0__ works.",
                ("__VITOU_TERM_0__",),
            ),
            (
                "Plain sentence.",
                (),
            ),
        ]
    )

    assert len(service.batch_calls) == 1

    assert results[0].fallback_used is True

    assert (
        results[0].text
        == "__VITOU_TERM_0__ works."
    )

    assert results[1].fallback_used is False

    assert (
        results[1].text
        == "Translated plain sentence."
    )


def test_single_text_api_uses_multi_text_batch_path():
    service = RecordingTranslator()

    result = service.translate_with_details(
        "First sentence. Second sentence."
    )

    assert len(service.batch_calls) == 1

    assert service.batch_calls[0] == [
        "First sentence.",
        "Second sentence.",
    ]

    assert result.sentence_count == 2
