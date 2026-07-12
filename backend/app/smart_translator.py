import html
import json
import time
from collections.abc import Callable
from typing import Any

from google.genai import types

from .terminology import protect_technical_terms, restore_technical_terms
from .translation_validation import validate_final_output, validate_raw_tags
from .translator import cleanup_final_output


SMART_MODEL = "gemini-3.1-flash-lite"
SMART_BATCH_MAX_ITEMS = 8
SMART_BATCH_MAX_CHARACTERS = 6000

SMART_MODE_SYSTEM_INSTRUCTION = """
You are the Smart translation engine for VitouLens AI.

Translate English Computer Science tutorial content into natural,
clear Khmer for a Cambodian Computer Science student.

Protected technical terms may appear inside semantic tags such as:

<vl-keep id="0">database</vl-keep>
<vl-preferred id="1">web browser</vl-preferred>

Rules:
1. Preserve every <vl-keep> and <vl-preferred> tag exactly.
2. Preserve each tag name, id, opening tag, closing tag, and inner text.
3. Never translate, rename, remove, duplicate, reorder, or invent tags.
4. Treat the inner text as part of the sentence meaning and context.
5. Keep each protected term in the same semantic relationship as the source.
6. Translate according to technical context, not word-for-word.
7. Preserve code, commands, URLs, acronyms, identifiers, and product names.
8. Do not add explanations or information absent from the source.
9. Preserve logical scope, plurality, negation, direction, cause and effect.
10. Do not merge separate actions, entities, or relationships from the source.
11. When multiple verbs share the same subject, preserve every verb as a
    separate action in the original order. Never turn a later verb into
    the destination, object, or modifier of an earlier verb.
12. Preserve references exactly: "the rest of X" means the remaining parts
    of the same X, not other X items.
12. Use natural Khmer sentence structure and readable punctuation.
13. Return only the translated content.
""".strip()


SMART_BATCH_SYSTEM_INSTRUCTION = (
    SMART_MODE_SYSTEM_INSTRUCTION.replace(
        "13. Return only the translated content.",
        (
            "13. Return only valid JSON matching the "
            "requested batch schema.\n"
            "14. Keep semantic tags inside each translation "
            "string exactly.\n"
            "15. Translate every batch item independently.\n"
            "16. Preserve every batch item id and item order "
            "exactly."
        ),
    )
)



def normalize_action(action: Any) -> str:
    value = getattr(action, "value", action)
    return str(value).strip().upper()


def build_term_policies(detected_terms: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "term": item.term,
            "action": normalize_action(item.action),
            "preferred_khmer": item.preferred_khmer,
        }
        for item in detected_terms
    ]


def make_gemini_semantic_tags(
    protected_text: str,
    placeholders: dict[str, str],
    detected_terms: list[Any],
) -> tuple[str, dict[str, str], list[dict[str, Any]]]:
    protected_detected_terms = [
        item
        for item in detected_terms
        if normalize_action(item.action) in {"KEEP", "PREFERRED"}
    ]
    if len(placeholders) != len(protected_detected_terms):
        raise ValueError(
            "Protected placeholder count does not match the number "
            "of KEEP/PREFERRED detected terms: "
            f"{len(placeholders)} placeholders vs "
            f"{len(protected_detected_terms)} protected terms."
        )

    gemini_text = protected_text
    tag_map: dict[str, str] = {}
    semantic_tags: list[dict[str, Any]] = []

    for index, ((placeholder, restored_value), detected_term) in enumerate(
        zip(placeholders.items(), protected_detected_terms, strict=True)
    ):
        action = normalize_action(detected_term.action)
        if action == "KEEP":
            tag_name = "vl-keep"
        elif action == "PREFERRED":
            tag_name = "vl-preferred"
        else:
            raise ValueError(f"Unsupported protected action: {action}")

        original_term = str(detected_term.term)
        escaped_term = html.escape(original_term, quote=False)
        semantic_tag = f'<{tag_name} id="{index}">{escaped_term}</{tag_name}>'
        placeholder_count = gemini_text.count(placeholder)
        if placeholder_count != 1:
            raise ValueError(
                f"Expected placeholder {placeholder!r} exactly once, "
                f"but found {placeholder_count} occurrences."
            )

        gemini_text = gemini_text.replace(placeholder, semantic_tag, 1)
        tag_map[semantic_tag] = placeholder
        semantic_tags.append(
            {
                "id": index,
                "tag": semantic_tag,
                "term": original_term,
                "action": action,
                "restored_value": restored_value,
            }
        )

    return gemini_text, tag_map, semantic_tags


def restore_gemini_semantic_tags(
    raw_output: str, tag_map: dict[str, str]
) -> str:
    restored_output = raw_output
    for semantic_tag, placeholder in tag_map.items():
        restored_output = restored_output.replace(semantic_tag, placeholder)
    return restored_output


def chunk_smart_texts(
    texts: list[str],
    *,
    max_items: int = SMART_BATCH_MAX_ITEMS,
    max_characters: int = SMART_BATCH_MAX_CHARACTERS,
) -> list[list[tuple[int, str]]]:
    if max_items < 1:
        raise ValueError(
            "Smart batch max_items must be positive."
        )

    if max_characters < 1:
        raise ValueError(
            "Smart batch max_characters must be positive."
        )

    chunks: list[list[tuple[int, str]]] = []
    current_chunk: list[tuple[int, str]] = []
    current_characters = 0

    for item_index, text in enumerate(texts):
        item_characters = len(text)

        should_flush = (
            current_chunk
            and (
                len(current_chunk) >= max_items
                or (
                    current_characters
                    + item_characters
                    > max_characters
                )
            )
        )

        if should_flush:
            chunks.append(current_chunk)
            current_chunk = []
            current_characters = 0

        current_chunk.append(
            (
                item_index,
                text,
            )
        )

        current_characters += item_characters

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def translate_many_with_gemini(
    client: Any,
    texts: list[str],
    domain: str,
    terms: list[Any],
    *,
    model: str = SMART_MODEL,
    retry_count: int = 3,
    sleep: Callable[[float], None] = time.sleep,
    max_items: int = SMART_BATCH_MAX_ITEMS,
    max_characters: int = SMART_BATCH_MAX_CHARACTERS,
) -> dict[str, Any]:
    chunks = chunk_smart_texts(
        texts,
        max_items=max_items,
        max_characters=max_characters,
    )

    started = time.perf_counter()

    results: list[dict[str, Any]] = []
    validation_issues: list[str] = []
    raw_outputs: list[str] = []

    for chunk_index, chunk in enumerate(chunks):
        contexts: list[dict[str, Any]] = []
        source_items: list[dict[str, str]] = []

        for item_index, source_text in chunk:
            (
                protected_text,
                placeholders,
                detected_terms,
            ) = protect_technical_terms(
                source_text,
                terms,
            )

            (
                gemini_text,
                tag_map,
                semantic_tags,
            ) = make_gemini_semantic_tags(
                protected_text,
                placeholders,
                detected_terms,
            )

            contexts.append(
                {
                    "item_index": item_index,
                    "source_text": source_text,
                    "placeholders": placeholders,
                    "tag_map": tag_map,
                    "semantic_tags": semantic_tags,
                    "detected_terms": build_term_policies(
                        detected_terms
                    ),
                    "protected_source": gemini_text,
                }
            )

            source_items.append(
                {
                    "id": str(item_index),
                    "source": gemini_text,
                }
            )

        prompt = (
            f"Technical domain: {domain}\n\n"
            "Translate every source item independently "
            "into Khmer.\n"
            "Return only valid JSON with exactly this shape:\n"
            '{"items":[{"id":"same source id",'
            '"translation":"translated content"}]}\n'
            "Return one result for every source item, "
            "in the same order.\n"
            "Preserve every id exactly.\n\n"
            "Source items:\n"
            + json.dumps(
                {
                    "items": source_items,
                },
                ensure_ascii=False,
            )
        )

        raw_output = ""

        for attempt in range(retry_count):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=(
                            SMART_BATCH_SYSTEM_INSTRUCTION
                        ),
                        temperature=0.1,
                        max_output_tokens=4096,
                    ),
                )

                raw_output = (
                    response.text or ""
                ).strip()

                if not raw_output:
                    raise RuntimeError(
                        "Gemini returned an empty "
                        "batch response."
                    )

                break

            except Exception:
                if attempt == retry_count - 1:
                    raise

                sleep(
                    2 ** (attempt + 1)
                )

        raw_outputs.append(raw_output)

        try:
            parsed_output = json.loads(raw_output)
        except json.JSONDecodeError:
            validation_issues.append(
                f"chunk_{chunk_index}:"
                "invalid_batch_json"
            )
            break

        returned_items = (
            parsed_output.get("items")
            if isinstance(parsed_output, dict)
            else None
        )

        if (
            not isinstance(returned_items, list)
            or len(returned_items) != len(contexts)
        ):
            validation_issues.append(
                f"chunk_{chunk_index}:"
                "invalid_batch_structure"
            )
            break

        valid_item_schema = all(
            isinstance(item, dict)
            and set(item) == {
                "id",
                "translation",
            }
            and isinstance(item.get("id"), str)
            and isinstance(
                item.get("translation"),
                str,
            )
            for item in returned_items
        )

        if not valid_item_schema:
            validation_issues.append(
                f"chunk_{chunk_index}:"
                "invalid_batch_item_schema"
            )
            break

        expected_ids = [
            str(context["item_index"])
            for context in contexts
        ]

        returned_ids = [
            item["id"]
            for item in returned_items
        ]

        if returned_ids != expected_ids:
            validation_issues.append(
                f"chunk_{chunk_index}:"
                "batch_item_ids_or_order_mismatch"
            )
            break

        for context, returned_item in zip(
            contexts,
            returned_items,
            strict=True,
        ):
            raw_translation = (
                returned_item["translation"].strip()
            )

            tag_validation = validate_raw_tags(
                raw_translation,
                context["tag_map"],
            )

            restored_semantic_tags = (
                restore_gemini_semantic_tags(
                    raw_translation,
                    context["tag_map"],
                )
            )

            candidate_output = cleanup_final_output(
                restore_technical_terms(
                    restored_semantic_tags,
                    context["placeholders"],
                )
            )

            output_validation = validate_final_output(
                context["source_text"],
                candidate_output,
            )

            item_issues = (
                tag_validation["issues"]
                + output_validation["issues"]
            )

            item_validation_passed = not item_issues

            if item_issues:
                validation_issues.extend(
                    (
                        f"item_{context['item_index']}:"
                        f"{issue}"
                    )
                    for issue in item_issues
                )

            results.append(
                {
                    "item_index": context["item_index"],
                    "output": (
                        candidate_output
                        if item_validation_passed
                        else None
                    ),
                    "rejected_output": (
                        None
                        if item_validation_passed
                        else candidate_output
                    ),
                    "raw_output": raw_translation,
                    "protected_source": (
                        context["protected_source"]
                    ),
                    "validation_passed": (
                        item_validation_passed
                    ),
                    "validation_issues": item_issues,
                    "tag_check_passed": (
                        tag_validation["passed"]
                    ),
                    "tag_validation": tag_validation,
                    "output_validation": output_validation,
                    "semantic_tags": (
                        context["semantic_tags"]
                    ),
                    "detected_terms": (
                        context["detected_terms"]
                    ),
                }
            )

    if (
        len(results) != len(texts)
        and not validation_issues
    ):
        validation_issues.append(
            "batch_result_count_mismatch"
        )

    elapsed = time.perf_counter() - started

    return {
        "results": results,
        "validation_passed": (
            not validation_issues
            and len(results) == len(texts)
            and all(
                item["validation_passed"]
                for item in results
            )
        ),
        "validation_issues": validation_issues,
        "chunk_count": len(chunks),
        "processed_chunk_count": len(raw_outputs),
        "time_seconds": round(elapsed, 3),
        "raw_outputs": raw_outputs,
    }


def translate_with_gemini(
    client: Any,
    text: str,
    domain: str,
    terms: list[Any],
    *,
    model: str = SMART_MODEL,
    retry_count: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    protected_text, placeholders, detected_terms = protect_technical_terms(text, terms)
    gemini_text, tag_map, semantic_tags = make_gemini_semantic_tags(
        protected_text, placeholders, detected_terms
    )
    prompt = f"Technical domain: {domain}\n\nSource content:\n{gemini_text}"
    started = time.perf_counter()
    raw_output = ""
    last_error: Exception | None = None

    for attempt in range(retry_count):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SMART_MODE_SYSTEM_INSTRUCTION,
                    temperature=0.1,
                    max_output_tokens=1200,
                ),
            )
            raw_output = (response.text or "").strip()
            if not raw_output:
                raise RuntimeError("Gemini returned an empty response.")
            last_error = None
            break
        except Exception as exc:
            last_error = exc
            if attempt == retry_count - 1:
                raise
            sleep(2 ** (attempt + 1))

    elapsed = time.perf_counter() - started
    tag_validation = validate_raw_tags(raw_output, tag_map)
    restored_semantic_tags = restore_gemini_semantic_tags(raw_output, tag_map)
    candidate_output = cleanup_final_output(
        restore_technical_terms(restored_semantic_tags, placeholders)
    )
    output_validation = validate_final_output(text, candidate_output)
    all_issues = tag_validation["issues"] + output_validation["issues"]
    validation_passed = not all_issues

    return {
        "output": candidate_output if validation_passed else None,
        "rejected_output": None if validation_passed else candidate_output,
        "raw_output": raw_output,
        "protected_source": gemini_text,
        "time_seconds": round(elapsed, 3),
        "validation_passed": validation_passed,
        "validation_issues": all_issues,
        "tag_check_passed": tag_validation["passed"],
        "tag_validation": tag_validation,
        "output_validation": output_validation,
        "semantic_tags": semantic_tags,
        "detected_terms": build_term_policies(detected_terms),
        "error": str(last_error) if last_error else None,
    }
