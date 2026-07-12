from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from .terminology import (
    TerminologyError,
    load_technical_terms,
    protect_technical_terms,
    restore_technical_terms,
)
from .translator import (
    TranslationServiceError,
    cleanup_final_output,
    translator_service,
)


class ProcessTextRequest(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(
                "Text must not be empty or whitespace only."
            )
        return value


app = FastAPI(
    title="VitouLens AI",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": "VitouLens AI",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/process-text")
def process_text(
    request: ProcessTextRequest,
) -> dict[str, object]:
    try:
        terms = load_technical_terms()

        (
            protected_text,
            placeholders,
            detected_terms,
        ) = protect_technical_terms(
            request.text,
            terms,
        )
    except TerminologyError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    try:
        translation = translator_service.translate_with_details(
            protected_text,
            placeholders.keys(),
        )
    except TranslationServiceError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    processed_text = cleanup_final_output(
        restore_technical_terms(
            translation.text,
            placeholders,
        )
    )

    detected_term_names = [
        detected.term
        for detected in detected_terms
    ]

    term_policies: list[dict[str, str]] = []

    for detected in detected_terms:
        policy = {
            "term": detected.term,
            "action": detected.action,
        }

        if detected.preferred_khmer is not None:
            policy["preferred_khmer"] = (
                detected.preferred_khmer
            )

        term_policies.append(policy)

    return {
        "original_text": request.text,
        "processed_text": processed_text,
        "detected_terms": detected_term_names,
        "term_policies": term_policies,
        "status": "translated",
    }