import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from google import genai


REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from backend.app.smart_translator import (
    SMART_MODEL,
    build_term_policies,
    translate_with_gemini,
)
from backend.app.terminology import (
    load_technical_terms,
    protect_technical_terms,
    restore_technical_terms,
)
from backend.app.translator import cleanup_final_output, translator_service


MODEL = SMART_MODEL
CASES_PATH = REPO_ROOT / "benchmark" / "cases.json"
RESULT_PATH = (
    REPO_ROOT / "benchmark" / "results" / "engine-benchmark-semantic-tags.json"
)
GEMINI_DELAY_SECONDS = 3.0


def load_cases() -> list[dict[str, str]]:
    data = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("Benchmark cases must contain a non-empty list.")
    return data


def translate_with_nllb(text: str, terms: list[Any]) -> dict[str, Any]:
    protected_text, placeholders, detected_terms = protect_technical_terms(text, terms)
    started = time.perf_counter()
    translation = translator_service.translate_with_details(
        protected_text, placeholders.keys()
    )
    elapsed = time.perf_counter() - started
    output = cleanup_final_output(
        restore_technical_terms(translation.text, placeholders)
    )
    return {
        "output": output,
        "time_seconds": round(elapsed, 3),
        "fallback_used": translation.fallback_used,
        "sentence_count": translation.sentence_count,
        "detected_terms": build_term_policies(detected_terms),
        "error": None,
    }


def main() -> None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY is missing.")

    cases = load_cases()
    terms = load_technical_terms()
    client = genai.Client(api_key=api_key)
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []

    print(f"Running {len(cases)} benchmark cases...")
    print(f"Gemini model: {MODEL}")
    print()

    for index, case in enumerate(cases, start=1):
        case_id = case["id"]
        domain = case["domain"]
        text = case["text"]
        print(f"[{index}/{len(cases)}] {case_id} — {domain}")
        case_result: dict[str, Any] = {
            "id": case_id,
            "domain": domain,
            "source_text": text,
        }

        try:
            nllb_result = translate_with_nllb(text, terms)
        except Exception as exc:
            nllb_result = {
                "output": None,
                "time_seconds": None,
                "error": str(exc),
            }

        try:
            gemini_result = translate_with_gemini(client, text, domain, terms)
        except Exception as exc:
            gemini_result = {
                "output": None,
                "rejected_output": None,
                "time_seconds": None,
                "validation_passed": False,
                "validation_issues": ["translation_exception"],
                "tag_check_passed": False,
                "error": str(exc),
            }

        case_result["nllb"] = nllb_result
        case_result["gemini"] = gemini_result
        results.append(case_result)

        print("  NLLB:", nllb_result.get("time_seconds"), "seconds")
        print("  Gemini:", gemini_result.get("time_seconds"), "seconds")
        print(
            "  Validation:",
            "PASS" if gemini_result.get("validation_passed") else "REJECT",
        )
        if gemini_result.get("validation_issues"):
            print("  Issues:", ", ".join(gemini_result["validation_issues"]))

        RESULT_PATH.write_text(
            json.dumps(
                {
                    "model": MODEL,
                    "protection_mode": "semantic-tags",
                    "case_count": len(cases),
                    "completed_case_count": len(results),
                    "results": results,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        if index < len(cases):
            time.sleep(GEMINI_DELAY_SECONDS)

    passed_count = sum(
        1 for item in results if item["gemini"].get("validation_passed")
    )
    rejected_count = len(results) - passed_count
    print()
    print(f"Completed {len(results)} cases.")
    print(f"Validation passed: {passed_count}")
    print(f"Validation rejected: {rejected_count}")
    print(f"Saved: {RESULT_PATH}")


if __name__ == "__main__":
    main()
