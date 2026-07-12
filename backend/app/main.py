from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from .terminology import (
    TerminologyError,
    load_technical_terms,
    protect_technical_terms,
    restore_technical_terms,
)


class ProcessTextRequest(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Text must not be empty or whitespace only.")
        return value


app = FastAPI(title="VitouLens AI", version="0.1.0")

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
async def process_text(request: ProcessTextRequest) -> dict[str, str | list[str]]:
    try:
        terms = load_technical_terms()
    except TerminologyError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    protected_text, placeholders, detected_terms = protect_technical_terms(
        request.text, terms
    )
    processed_text = restore_technical_terms(protected_text, placeholders)

    return {
        "original_text": request.text,
        "processed_text": processed_text,
        "detected_terms": detected_terms,
        "status": "received",
    }
