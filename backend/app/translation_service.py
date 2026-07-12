import os
from collections.abc import Callable
from typing import Any

from google import genai

from .smart_translator import (
    SMART_MODEL,
    translate_many_with_gemini,
    translate_with_gemini,
)
from .terminology import (
    load_technical_terms,
    protect_technical_terms,
    restore_technical_terms,
)
from .translator import (
    TranslationError,
    cleanup_final_output,
    translator_service,
)


class SmartModeUnavailableError(Exception):
    """Raised when Smart Mode is not configured."""


class SmartTranslationError(Exception):
    """Raised when Gemini cannot produce a response."""


class SmartTranslationRejectedError(Exception):
    """Raised when strict validation rejects Gemini output."""


def create_gemini_client(api_key: str) -> Any:
    return genai.Client(api_key=api_key)


class TranslationOrchestrator:
    def __init__(
        self,
        *,
        basic_translator: Any = translator_service,
        api_key_provider: Callable[[], str | None] | None = None,
        smart_client_factory: Callable[[str], Any] = create_gemini_client,
        smart_translate: Callable[..., dict[str, Any]] = translate_with_gemini,
        smart_translate_many: Callable[
            ...,
            dict[str, Any],
        ] = translate_many_with_gemini,
    ) -> None:
        self._basic_translator = basic_translator
        self._api_key_provider = api_key_provider or (
            lambda: os.getenv("GEMINI_API_KEY")
        )
        self._smart_client_factory = smart_client_factory
        self._smart_translate = smart_translate
        self._smart_translate_many = smart_translate_many

    @staticmethod
    def _term_metadata(
        detected_terms: list[Any],
    ) -> tuple[list[str], list[dict[str, str]]]:
        detected_term_names = [detected.term for detected in detected_terms]
        term_policies: list[dict[str, str]] = []

        for detected in detected_terms:
            policy = {
                "term": detected.term,
                "action": detected.action,
            }
            if detected.preferred_khmer is not None:
                policy["preferred_khmer"] = detected.preferred_khmer
            term_policies.append(policy)

        return detected_term_names, term_policies

    def translate_basic_many(
        self,
        texts: list[str],
    ) -> list[dict[str, object]]:
        terms = load_technical_terms()

        contexts: list[
            tuple[
                str,
                dict[str, str],
                list[Any],
            ]
        ] = []

        batch_items: list[
            tuple[str, tuple[str, ...]]
        ] = []

        for text in texts:
            (
                protected_text,
                placeholders,
                detected_terms,
            ) = protect_technical_terms(
                text,
                terms,
            )

            contexts.append(
                (
                    text,
                    placeholders,
                    detected_terms,
                )
            )

            batch_items.append(
                (
                    protected_text,
                    tuple(placeholders.keys()),
                )
            )

        translations = (
            self._basic_translator
            .translate_many_with_details(
                batch_items
            )
        )

        if len(translations) != len(contexts):
            raise TranslationError(
                "Local NLLB batch translation returned "
                "an unexpected item count."
            )

        results: list[
            dict[str, object]
        ] = []

        for (
            (
                original_text,
                placeholders,
                detected_terms,
            ),
            translation,
        ) in zip(
            contexts,
            translations,
            strict=True,
        ):
            processed_text = cleanup_final_output(
                restore_technical_terms(
                    translation.text,
                    placeholders,
                )
            )

            (
                detected_term_names,
                term_policies,
            ) = self._term_metadata(
                detected_terms
            )

            results.append(
                {
                    "original_text": original_text,
                    "processed_text": processed_text,
                    "detected_terms": (
                        detected_term_names
                    ),
                    "term_policies": term_policies,
                    "status": "translated",
                }
            )

        return results

    def translate_basic(
        self,
        text: str,
    ) -> dict[str, object]:
        return self.translate_basic_many(
            [text]
        )[0]

    def translate_smart_many(
        self,
        texts: list[str],
        domain: str,
    ) -> list[dict[str, object]]:
        api_key = self._api_key_provider()

        if not api_key:
            raise SmartModeUnavailableError

        terms = load_technical_terms()

        try:
            client = self._smart_client_factory(
                api_key
            )

            result = self._smart_translate_many(
                client,
                texts,
                domain,
                terms,
            )
        except Exception as exc:
            raise SmartTranslationError from exc

        if not isinstance(result, dict):
            raise SmartTranslationRejectedError

        batch_validation_passed = (
            result.get("validation_passed") is True
        )

        batch_results = result.get("results")

        if (
            not batch_validation_passed
            or not isinstance(batch_results, list)
            or len(batch_results) != len(texts)
        ):
            raise SmartTranslationRejectedError

        public_results: list[
            dict[str, object]
        ] = []

        for item_index, (
            original_text,
            item,
        ) in enumerate(
            zip(
                texts,
                batch_results,
                strict=True,
            )
        ):
            if (
                not isinstance(item, dict)
                or item.get("item_index")
                != item_index
            ):
                raise SmartTranslationRejectedError

            output = item.get("output")

            item_validation_passed = (
                item.get("validation_passed")
                is True
            )

            if (
                not item_validation_passed
                or not isinstance(output, str)
                or not output.strip()
            ):
                raise SmartTranslationRejectedError

            term_policies = item.get(
                "detected_terms"
            )

            if not isinstance(
                term_policies,
                list,
            ):
                term_policies = []

            detected_term_names = [
                term["term"]
                for term in term_policies
                if (
                    isinstance(term, dict)
                    and isinstance(
                        term.get("term"),
                        str,
                    )
                )
            ]

            public_results.append(
                {
                    "original_text": original_text,
                    "processed_text": output,
                    "detected_terms": (
                        detected_term_names
                    ),
                    "term_policies": term_policies,
                    "status": "translated",
                    "mode": "smart",
                    "engine": SMART_MODEL,
                    "validation_passed": True,
                    "translation": output,
                }
            )

        return public_results

    def translate_smart(self, text: str, domain: str) -> dict[str, object]:
        api_key = self._api_key_provider()
        if not api_key:
            raise SmartModeUnavailableError

        terms = load_technical_terms()

        try:
            client = self._smart_client_factory(api_key)
            result = self._smart_translate(client, text, domain, terms)
        except Exception as exc:
            raise SmartTranslationError from exc

        output = result.get("output")
        validation_passed = result.get("validation_passed") is True
        if not validation_passed or not isinstance(output, str) or not output.strip():
            raise SmartTranslationRejectedError

        term_policies = result.get("detected_terms")
        if not isinstance(term_policies, list):
            term_policies = []
        detected_term_names = [
            item["term"]
            for item in term_policies
            if isinstance(item, dict) and isinstance(item.get("term"), str)
        ]

        return {
            "original_text": text,
            "processed_text": output,
            "detected_terms": detected_term_names,
            "term_policies": term_policies,
            "status": "translated",
            "mode": "smart",
            "engine": SMART_MODEL,
            "validation_passed": True,
            "translation": output,
        }


translation_orchestrator = TranslationOrchestrator()
