import os
from collections.abc import Callable
from typing import Any

from google import genai

from .smart_translator import SMART_MODEL, translate_with_gemini
from .terminology import (
    load_technical_terms,
    protect_technical_terms,
    restore_technical_terms,
)
from .translator import cleanup_final_output, translator_service


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
        api_key_provider: Callable[[], str | None] | None = None,
        smart_client_factory: Callable[[str], Any] = create_gemini_client,
        smart_translate: Callable[..., dict[str, Any]] = translate_with_gemini,
    ) -> None:
        self._api_key_provider = api_key_provider or (
            lambda: os.getenv("GEMINI_API_KEY")
        )
        self._smart_client_factory = smart_client_factory
        self._smart_translate = smart_translate

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

    def translate_basic(self, text: str) -> dict[str, object]:
        terms = load_technical_terms()
        protected_text, placeholders, detected_terms = protect_technical_terms(
            text, terms
        )
        translation = translator_service.translate_with_details(
            protected_text, placeholders.keys()
        )
        processed_text = cleanup_final_output(
            restore_technical_terms(translation.text, placeholders)
        )
        detected_term_names, term_policies = self._term_metadata(detected_terms)

        return {
            "original_text": text,
            "processed_text": processed_text,
            "detected_terms": detected_term_names,
            "term_policies": term_policies,
            "status": "translated",
        }

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
