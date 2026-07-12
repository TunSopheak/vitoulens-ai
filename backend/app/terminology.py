import json
import re
from dataclasses import dataclass
from pathlib import Path


DEFAULT_TERMS_PATH = Path(__file__).resolve().parents[2] / "data" / "technical_terms.json"
VALID_ACTIONS = {"KEEP", "TRANSLATE", "PREFERRED"}


class TerminologyError(Exception):
    """Raised when technical terminology data cannot be loaded."""


@dataclass(frozen=True)
class TerminologyEntry:
    term: str
    action: str
    preferred_khmer: str | None = None


@dataclass(frozen=True)
class DetectedTerm:
    term: str
    action: str
    preferred_khmer: str | None = None


def load_technical_terms(path: Path | None = None) -> list[TerminologyEntry]:
    terms_path = path or DEFAULT_TERMS_PATH

    try:
        data = json.loads(terms_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise TerminologyError(
            f"Technical terms file not found: {terms_path}"
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise TerminologyError(
            f"Could not read technical terms file: {terms_path}"
        ) from exc

    if not isinstance(data, list) or not data:
        raise TerminologyError(
            "Technical terms file must contain a non-empty list."
        )

    entries: dict[str, TerminologyEntry] = {}

    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise TerminologyError(
                f"Technical term entry {index} must be an object."
            )

        term = item.get("term")
        action = item.get("action")
        preferred_khmer = item.get("preferred_khmer")

        if not isinstance(term, str) or not term.strip():
            raise TerminologyError(
                f"Technical term entry {index} requires a term."
            )

        if action not in VALID_ACTIONS:
            raise TerminologyError(
                f"Technical term entry {index} action must be "
                "KEEP, TRANSLATE, or PREFERRED."
            )

        normalized_preferred: str | None = None

        if action == "PREFERRED":
            if (
                not isinstance(preferred_khmer, str)
                or not preferred_khmer.strip()
            ):
                raise TerminologyError(
                    f"PREFERRED technical term entry {index} "
                    "requires preferred_khmer."
                )
            normalized_preferred = preferred_khmer.strip()

        normalized_term = term.strip()
        key = normalized_term.casefold()

        if key in entries:
            raise TerminologyError(
                f"Duplicate technical term: {normalized_term}"
            )

        entries[key] = TerminologyEntry(
            term=normalized_term,
            action=action,
            preferred_khmer=normalized_preferred,
        )

    return sorted(
        entries.values(),
        key=lambda entry: len(entry.term),
        reverse=True,
    )


def _entry_expression(entry: TerminologyEntry) -> str:
    expression = re.escape(entry.term)

    if (
        entry.term[-1].isalpha()
        and not entry.term.casefold().endswith("s")
    ):
        expression += "s?"

    return expression


def _term_pattern(
    entries: list[TerminologyEntry],
) -> re.Pattern[str]:
    alternatives = [
        f"(?P<term_{index}>{_entry_expression(entry)})"
        for index, entry in enumerate(entries)
    ]

    return re.compile(
        rf"(?<!\w)(?:{'|'.join(alternatives)})(?!\w)",
        re.IGNORECASE,
    )


def _matching_entry(
    match: re.Match[str],
    entries: list[TerminologyEntry],
) -> TerminologyEntry:
    return entries[
        int(match.lastgroup.removeprefix("term_"))
    ]


def detect_technical_terms(
    text: str,
    entries: list[TerminologyEntry],
) -> list[DetectedTerm]:
    if not text or not entries:
        return []

    detected_terms: list[DetectedTerm] = []

    for match in _term_pattern(entries).finditer(text):
        entry = _matching_entry(match, entries)

        detected_terms.append(
            DetectedTerm(
                term=match.group(0),
                action=entry.action,
                preferred_khmer=entry.preferred_khmer,
            )
        )

    return detected_terms


def protect_technical_terms(
    text: str,
    entries: list[TerminologyEntry],
) -> tuple[str, dict[str, str], list[DetectedTerm]]:
    if not text or not entries:
        return text, {}, []

    placeholders: dict[str, str] = {}
    detected_terms: list[DetectedTerm] = []
    placeholder_index = 0

    def apply_policy(match: re.Match[str]) -> str:
        nonlocal placeholder_index

        original_term = match.group(0)
        entry = _matching_entry(match, entries)

        detected_terms.append(
            DetectedTerm(
                term=original_term,
                action=entry.action,
                preferred_khmer=entry.preferred_khmer,
            )
        )

        if entry.action == "TRANSLATE":
            return original_term

        placeholder = f"__VITOU_TERM_{placeholder_index}__"

        while placeholder in text:
            placeholder_index += 1
            placeholder = f"__VITOU_TERM_{placeholder_index}__"

        if entry.action == "PREFERRED":
            replacement = entry.preferred_khmer
            if replacement is None:
                raise TerminologyError(
                    f"PREFERRED term '{entry.term}' "
                    "has no preferred Khmer value."
                )
        else:
            replacement = original_term

        placeholders[placeholder] = replacement
        placeholder_index += 1

        return placeholder

    protected_text = _term_pattern(entries).sub(
        apply_policy,
        text,
    )

    return protected_text, placeholders, detected_terms


def restore_technical_terms(
    text: str,
    placeholders: dict[str, str],
) -> str:
    restored_text = text

    for placeholder, replacement in placeholders.items():
        restored_text = restored_text.replace(
            placeholder,
            replacement,
        )

    return restored_text