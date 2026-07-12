import re
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from threading import Lock
from typing import Any, Iterable


MODEL_NAME = "facebook/nllb-200-distilled-600M"
MODEL_PATH = (
    Path(__file__).resolve().parents[1]
    / "models"
    / "nllb-200-distilled-600M-ct2"
)
SOURCE_LANGUAGE = "eng_Latn"
TARGET_LANGUAGE = "khm_Khmr"


class TranslationServiceError(Exception):
    """Base error for local translation failures."""


class ModelDirectoryMissingError(TranslationServiceError):
    """Raised when the converted CTranslate2 model is unavailable."""


class ModelLoadingError(TranslationServiceError):
    """Raised when the translator or tokenizer cannot be loaded."""


class TranslationError(TranslationServiceError):
    """Raised when local inference fails."""


@dataclass(frozen=True)
class TranslationResult:
    text: str
    sentence_count: int
    fallback_used: bool


class NLLBTranslatorService:
    def __init__(self, model_path: Path = MODEL_PATH) -> None:
        self.model_path = model_path
        self._translator: Any | None = None
        self._tokenizer: Any | None = None
        self._load_lock = Lock()

    @property
    def is_loaded(self) -> bool:
        return self._translator is not None and self._tokenizer is not None

    def _ensure_loaded(self) -> None:
        if self.is_loaded:
            return
        if not self.model_path.is_dir():
            raise ModelDirectoryMissingError(
                f"Converted NLLB model directory not found: {self.model_path}"
            )

        with self._load_lock:
            if self.is_loaded:
                return

            try:
                ctranslate2 = import_module("ctranslate2")
                transformers = import_module("transformers")
                translator = ctranslate2.Translator(
                    str(self.model_path), device="cpu", compute_type="int8"
                )
                tokenizer = transformers.AutoTokenizer.from_pretrained(
                    str(self.model_path),
                    src_lang=SOURCE_LANGUAGE,
                    local_files_only=True,
                )
            except Exception as exc:
                raise ModelLoadingError(
                    "Failed to load the local NLLB translator or tokenizer."
                ) from exc

            self._translator = translator
            self._tokenizer = tokenizer

    def _translate_batch(self, sentences: list[str]) -> list[str]:
        self._ensure_loaded()

        try:
            source_tokens = [
                self._tokenizer.convert_ids_to_tokens(
                    self._tokenizer.encode(sentence)
                )
                for sentence in sentences
            ]
            results = self._translator.translate_batch(
                source_tokens,
                target_prefix=[[TARGET_LANGUAGE] for _ in source_tokens],
            )
            translated_sentences = []
            for result in results:
                target_tokens = result.hypotheses[0][1:]
                target_ids = self._tokenizer.convert_tokens_to_ids(target_tokens)
                translated_sentences.append(
                    self._tokenizer.decode(target_ids, skip_special_tokens=True)
                )
        except Exception as exc:
            raise TranslationError("Local NLLB translation failed.") from exc

        if len(translated_sentences) != len(sentences) or any(
            not sentence for sentence in translated_sentences
        ):
            raise TranslationError("Local NLLB translation returned an empty result.")
        return translated_sentences

    @staticmethod
    def _split_sentences(text: str) -> tuple[list[str], list[str]]:
        parts = re.split(r"(?<=[.!?។៕])(\s+)", text)
        return parts[::2], parts[1::2]

    @staticmethod
    def _clean_output(text: str) -> str:
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\s+([,.!?;:។៕])", r"\1", text)
        text = re.sub(r"([.!?។៕])(?:\s*\1)+", r"\1", text)
        for spaced_phrase, compact_phrase in (
            ("គឺ ជា", "គឺជា"),
            ("ដំណើរ ការ", "ដំណើរការ"),
            ("ដោយ សុវត្ថិភាព", "ដោយសុវត្ថិភាព"),
            ("ដោយ ប្រើ", "ដោយប្រើ"),
        ):
            text = text.replace(spaced_phrase, compact_phrase)
        return text.strip()

    @staticmethod
    def _preserve_terminal_punctuation(source: str, translated: str) -> str:
        source_punctuation = re.search(r"[.!?។៕]+$", source)
        translated_punctuation = re.search(r"[.!?។៕]+$", translated)
        if source_punctuation and not translated_punctuation:
            return translated + source_punctuation.group(0)
        return translated

    @staticmethod
    def _add_surrogates(
        sentence: str, placeholders: tuple[str, ...]
    ) -> tuple[str, dict[str, str]]:
        surrogates: dict[str, str] = {}
        protected_sentence = sentence

        for index, placeholder in enumerate(placeholders):
            if placeholder not in protected_sentence:
                continue
            surrogate = f"XQZ{index}ZQX"
            while surrogate in protected_sentence:
                surrogate = f"XQZ{surrogate}ZQX"
            protected_sentence = protected_sentence.replace(placeholder, surrogate)
            surrogates[surrogate] = placeholder

        return protected_sentence, surrogates

    def translate_many_with_details(
        self,
        items: list[tuple[str, Iterable[str]]],
    ) -> list[TranslationResult]:
        normalized_items = [
            (
                text,
                tuple(placeholders),
            )
            for text, placeholders in items
        ]

        if not normalized_items:
            return []

        item_sentence_parts: list[list[str]] = []
        item_separators: list[list[str]] = []
        item_sentence_counts: list[int] = []
        item_fallback_used = [
            False
            for _ in normalized_items
        ]

        prepared_sentences: list[str] = []

        sentence_contexts: list[
            tuple[
                int,
                int,
                str,
                dict[str, str],
            ]
        ] = []

        for item_index, (
            text,
            protected_placeholders,
        ) in enumerate(normalized_items):
            sentence_parts, separators = (
                self._split_sentences(text)
            )

            sentence_indexes = [
                index
                for index, sentence in enumerate(
                    sentence_parts
                )
                if sentence.strip()
            ]

            item_sentence_parts.append(
                sentence_parts
            )

            item_separators.append(
                separators
            )

            item_sentence_counts.append(
                len(sentence_indexes)
            )

            for sentence_index in sentence_indexes:
                prepared, surrogates = (
                    self._add_surrogates(
                        sentence_parts[
                            sentence_index
                        ].strip(),
                        protected_placeholders,
                    )
                )

                prepared_sentences.append(
                    prepared
                )

                sentence_contexts.append(
                    (
                        item_index,
                        sentence_index,
                        prepared,
                        surrogates,
                    )
                )

        translated_sentences = (
            self._translate_batch(
                prepared_sentences
            )
            if prepared_sentences
            else []
        )

        for (
            (
                item_index,
                sentence_index,
                source,
                surrogates,
            ),
            translated,
        ) in zip(
            sentence_contexts,
            translated_sentences,
            strict=True,
        ):
            markers_intact = all(
                translated.count(surrogate) == 1
                for surrogate in surrogates
            )

            if not markers_intact:
                item_fallback_used[
                    item_index
                ] = True

                continue

            restored_sentence = translated

            for (
                surrogate,
                placeholder,
            ) in surrogates.items():
                restored_sentence = (
                    restored_sentence.replace(
                        surrogate,
                        placeholder,
                    )
                )

            restored_sentence = (
                self._clean_output(
                    restored_sentence
                )
            )

            item_sentence_parts[
                item_index
            ][sentence_index] = (
                self._preserve_terminal_punctuation(
                    source,
                    restored_sentence,
                )
            )

        results: list[TranslationResult] = []

        for item_index, sentence_parts in enumerate(
            item_sentence_parts
        ):
            separators = item_separators[
                item_index
            ]

            rebuilt_text = "".join(
                sentence
                + (
                    separators[index]
                    if index < len(separators)
                    else ""
                )
                for index, sentence in enumerate(
                    sentence_parts
                )
            )

            results.append(
                TranslationResult(
                    text=self._clean_output(
                        rebuilt_text
                    ),
                    sentence_count=(
                        item_sentence_counts[
                            item_index
                        ]
                    ),
                    fallback_used=(
                        item_fallback_used[
                            item_index
                        ]
                    ),
                )
            )

        return results

    def translate_with_details(
        self,
        text: str,
        placeholders: Iterable[str] = (),
    ) -> TranslationResult:
        return self.translate_many_with_details(
            [
                (
                    text,
                    placeholders,
                )
            ]
        )[0]

    def translate(
        self,
        text: str,
        placeholders: Iterable[str] = (),
    ) -> str:
        return self.translate_with_details(
            text,
            placeholders,
        ).text



def cleanup_final_output(text: str) -> str:
    """Conservatively normalize final Khmer translation spacing."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(
        r"\s+([,!?;:\u17d4\u17d5])",
        r"\1",
        text,
    )
    text = re.sub(
        r"([\u17d4\u17d5!?])(?:\s*\1)+",
        r"\1",
        text,
    )

    exact_replacements = (
        (
            "\u17a2\u17d2\u1793\u1780 \u1794\u17d2\u179a\u17be "
            "\u1794\u17d2\u179a\u17b6\u179f\u17cb",
            "\u17a2\u17d2\u1793\u1780\u1794\u17d2\u179a\u17be"
            "\u1794\u17d2\u179a\u17b6\u179f\u17cb",
        ),
        (
            "\u178a\u17c6\u178e\u17be\u179a \u1780\u17b6\u179a",
            "\u178a\u17c6\u178e\u17be\u179a\u1780\u17b6\u179a",
        ),
    )

    for spaced, compact in exact_replacements:
        text = text.replace(spaced, compact)

    attach_next = (
        "\u1782\u17ba\u1787\u17b6",
        "\u178a\u17c6\u178e\u17be\u179a\u1780\u17b6\u179a",
        "\u1793\u17b7\u1784",
        "\u178a\u17c2\u179b",
        "\u179b\u17be",
        "\u1791\u17c5",
        "\u178a\u17c4\u1799",
        "\u1794\u17d2\u179a\u17be",
        "\u178f\u17b6\u1798\u179a\u1799\u17c8",
        "\u1780\u17b6\u1793\u17cb",
    )

    for word in attach_next:
        text = re.sub(
            rf"({re.escape(word)}) +(?=[\u1780-\u17ff])",
            r"\1",
            text,
        )

    attach_previous = (
        "\u179c\u17b7\u1789",
    )

    for word in attach_previous:
        text = re.sub(
            rf"(?<=[\u1780-\u17ff]) +({re.escape(word)})",
            r"\1",
            text,
        )

    if re.search(r"[\u1780-\u17ff]", text):
        text = re.sub(
            r"\.(?=\s|$)",
            "\u17d4",
            text,
        )

    return text.strip()


translator_service = NLLBTranslatorService()
