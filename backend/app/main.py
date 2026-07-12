from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from .terminology import TerminologyError
from .translation_service import (
    SmartModeUnavailableError,
    SmartTranslationError,
    SmartTranslationRejectedError,
    TranslationOrchestrator,
    translation_orchestrator,
)
from .translator import TranslationServiceError


class ProcessTextRequest(BaseModel):
    text: str
    mode: Literal["basic", "smart"] = "basic"
    domain: str = "Computer Science"

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Text must not be empty or whitespace only.")
        return value

    @field_validator("domain")
    @classmethod
    def domain_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Domain must not be empty or whitespace only.")
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


def get_translation_orchestrator() -> TranslationOrchestrator:
    return translation_orchestrator


@app.post("/process-text")
def process_text(
    request: ProcessTextRequest,
    service: Annotated[
        TranslationOrchestrator,
        Depends(get_translation_orchestrator),
    ],
) -> dict[str, object]:
    try:
        if request.mode == "smart":
            return service.translate_smart(request.text, request.domain)
        return service.translate_basic(request.text)
    except TerminologyError as exc:
        raise HTTPException(
            status_code=500,
            detail="Terminology configuration is unavailable.",
        ) from exc
    except TranslationServiceError as exc:
        raise HTTPException(
            status_code=503,
            detail="Basic translation service is unavailable.",
        ) from exc
    except SmartModeUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail="Smart translation is not configured.",
        ) from exc
    except SmartTranslationRejectedError as exc:
        raise HTTPException(
            status_code=502,
            detail="Smart translation output failed validation.",
        ) from exc
    except SmartTranslationError as exc:
        raise HTTPException(
            status_code=502,
            detail="Smart translation service request failed.",
        ) from exc
