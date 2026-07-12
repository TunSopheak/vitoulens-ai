import json
import re
from pathlib import Path


DEFAULT_TERMS_PATH = Path(__file__).resolve().parents[2] / "data" / "technical_terms.json"


class TerminologyError(Exception):
    """Raised when technical terminology data cannot be loaded."""


def load_technical_terms(path: Path | None = None) -> list[str]:
    terms_path = path or DEFAULT_TERMS_PATH

    try:
        data = json.loads(terms_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise TerminologyError(f"Technical terms file not found: {terms_path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise TerminologyError(f"Could not read technical terms file: {terms_path}") from exc

    terms = data.get("terms") if isinstance(data, dict) else None
    if not isinstance(terms, list) or not terms:
        raise TerminologyError("Technical terms file must contain a non-empty 'terms' list.")
    if any(not isinstance(term, str) or not term.strip() for term in terms):
        raise TerminologyError("Every technical term must be a non-empty string.")

    unique_terms = {term.casefold(): term for term in terms}
    return sorted(unique_terms.values(), key=len, reverse=True)


def _term_pattern(terms: list[str]) -> re.Pattern[str]:
    alternatives = "|".join(re.escape(term) for term in sorted(terms, key=len, reverse=True))
    return re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)", re.IGNORECASE)


def detect_technical_terms(text: str, terms: list[str]) -> list[str]:
    if not text or not terms:
        return []
    return [match.group(0) for match in _term_pattern(terms).finditer(text)]


def protect_technical_terms(
    text: str, terms: list[str]
) -> tuple[str, dict[str, str], list[str]]:
    if not text or not terms:
        return text, {}, []

    placeholders: dict[str, str] = {}
    detected_terms: list[str] = []
    placeholder_index = 0

    def replace_term(match: re.Match[str]) -> str:
        nonlocal placeholder_index
        original_term = match.group(0)
        placeholder = f"__VITOU_TERM_{placeholder_index}__"
        while placeholder in text:
            placeholder_index += 1
            placeholder = f"__VITOU_TERM_{placeholder_index}__"

        placeholders[placeholder] = original_term
        detected_terms.append(original_term)
        placeholder_index += 1
        return placeholder

    protected_text = _term_pattern(terms).sub(replace_term, text)
    return protected_text, placeholders, detected_terms


def restore_technical_terms(text: str, placeholders: dict[str, str]) -> str:
    restored_text = text
    for placeholder, original_term in placeholders.items():
        restored_text = restored_text.replace(placeholder, original_term)
    return restored_text
