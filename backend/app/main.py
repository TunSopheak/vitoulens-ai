from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from .terminology import TerminologyError
from .translation_service import (
    SmartModeUnavailableError,
    SmartTranslationError,
    SmartTranslationRejectedError,
    TranslationOrchestrator,
    translation_orchestrator,
)
from .translator import (
    MODEL_NAME,
    TranslationServiceError,
)


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



class ProcessBatchItem(BaseModel):
    id: str = Field(
        min_length=1,
        max_length=100,
    )
    text: str = Field(
        min_length=1,
        max_length=5000,
    )

    @field_validator("id")
    @classmethod
    def id_must_not_be_blank(
        cls,
        value: str,
    ) -> str:
        if not value.strip():
            raise ValueError(
                "Batch item ID must not be blank."
            )
        return value

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(
        cls,
        value: str,
    ) -> str:
        if not value.strip():
            raise ValueError(
                "Batch item text must not be blank."
            )
        return value


class ProcessBatchRequest(BaseModel):
    items: list[ProcessBatchItem] = Field(
        min_length=1,
        max_length=200,
    )
    mode: Literal["basic", "smart"] = "basic"
    domain: str = "Computer Science"

    @field_validator("items")
    @classmethod
    def item_ids_must_be_unique(
        cls,
        value: list[ProcessBatchItem],
    ) -> list[ProcessBatchItem]:
        item_ids = [
            item.id
            for item in value
        ]

        if len(item_ids) != len(set(item_ids)):
            raise ValueError(
                "Batch item IDs must be unique."
            )

        return value

    @field_validator("domain")
    @classmethod
    def domain_must_not_be_blank(
        cls,
        value: str,
    ) -> str:
        if not value.strip():
            raise ValueError(
                "Domain must not be empty "
                "or whitespace only."
            )
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



@app.post("/process-batch")
def process_batch(
    request: ProcessBatchRequest,
    service: Annotated[
        TranslationOrchestrator,
        Depends(get_translation_orchestrator),
    ],
) -> dict[str, object]:
    try:
        texts = [
            item.text
            for item in request.items
        ]

        if request.mode == "smart":
            translations = service.translate_smart_many(
                texts,
                request.domain,
            )
        else:
            translations = service.translate_basic_many(
                texts
            )

        if len(translations) != len(request.items):
            if request.mode == "smart":
                raise SmartTranslationRejectedError

            raise TranslationServiceError(
                "Basic batch translation returned "
                "an unexpected item count."
            )

        results: list[dict[str, str]] = []

        for item, translation in zip(
            request.items,
            translations,
            strict=True,
        ):
            translated_text = translation.get(
                "translation"
                if request.mode == "smart"
                else "processed_text"
            )

            if (
                not isinstance(translated_text, str)
                or not translated_text.strip()
            ):
                if request.mode == "smart":
                    raise SmartTranslationRejectedError

                raise TranslationServiceError(
                    "Basic batch translation returned "
                    "an invalid result."
                )

            results.append(
                {
                    "id": item.id,
                    "translation": translated_text,
                }
            )

        response: dict[str, object] = {
            "mode": request.mode,
            "engine": (
                translations[0]["engine"]
                if request.mode == "smart"
                else MODEL_NAME
            ),
            "results": results,
        }

        if request.mode == "smart":
            response["validation_passed"] = True

        return response

    except TerminologyError as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Terminology configuration "
                "is unavailable."
            ),
        ) from exc

    except TranslationServiceError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Basic translation service "
                "is unavailable."
            ),
        ) from exc

    except SmartModeUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Smart translation is not configured."
            ),
        ) from exc

    except SmartTranslationRejectedError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "Smart translation output "
                "failed validation."
            ),
        ) from exc

    except SmartTranslationError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "Smart translation service "
                "request failed."
            ),
        ) from exc


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
