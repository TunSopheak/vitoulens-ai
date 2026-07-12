from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.main import (
    app,
    get_translation_orchestrator,
)
from backend.app.terminology import (
    TerminologyError,
)
from backend.app.translator import (
    MODEL_NAME,
    TranslationServiceError,
)


class FakeBatchOrchestrator:
    def __init__(self) -> None:
        self.batch_calls: list[list[str]] = []
        self.smart_batch_calls: list[
            tuple[list[str], str]
        ] = []

    def translate_basic_many(
        self,
        texts: list[str],
    ) -> list[dict[str, object]]:
        self.batch_calls.append(
            list(texts)
        )

        return [
            {
                "original_text": text,
                "processed_text": (
                    f"Translated: {text}"
                ),
                "detected_terms": [],
                "term_policies": [],
                "status": "translated",
            }
            for text in texts
        ]

    def translate_smart_many(
        self,
        texts: list[str],
        domain: str,
    ) -> list[dict[str, object]]:
        self.smart_batch_calls.append(
            (
                list(texts),
                domain,
            )
        )

        return [
            {
                "original_text": text,
                "processed_text": (
                    f"Smart: {text}"
                ),
                "detected_terms": [],
                "term_policies": [],
                "status": "translated",
                "mode": "smart",
                "engine": "gemini-3.1-flash-lite",
                "validation_passed": True,
                "translation": (
                    f"Smart: {text}"
                ),
            }
            for text in texts
        ]


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def override_service(service: Any) -> None:
    app.dependency_overrides[
        get_translation_orchestrator
    ] = lambda: service


def test_basic_batch_preserves_ids_and_order(
    client: TestClient,
) -> None:
    service = FakeBatchOrchestrator()
    override_service(service)

    response = client.post(
        "/process-batch",
        json={
            "items": [
                {
                    "id": "block-0",
                    "text": "First block.",
                },
                {
                    "id": "block-1",
                    "text": "Second block.",
                },
            ],
            "mode": "basic",
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "mode": "basic",
        "engine": MODEL_NAME,
        "results": [
            {
                "id": "block-0",
                "translation": (
                    "Translated: First block."
                ),
            },
            {
                "id": "block-1",
                "translation": (
                    "Translated: Second block."
                ),
            },
        ],
    }

    assert service.batch_calls == [
        [
            "First block.",
            "Second block.",
        ]
    ]


def test_empty_batch_returns_422(
    client: TestClient,
) -> None:
    service = FakeBatchOrchestrator()
    override_service(service)

    response = client.post(
        "/process-batch",
        json={
            "items": [],
            "mode": "basic",
        },
    )

    assert response.status_code == 422
    assert service.batch_calls == []


def test_duplicate_batch_ids_return_422(
    client: TestClient,
) -> None:
    service = FakeBatchOrchestrator()
    override_service(service)

    response = client.post(
        "/process-batch",
        json={
            "items": [
                {
                    "id": "block-0",
                    "text": "First block.",
                },
                {
                    "id": "block-0",
                    "text": "Second block.",
                },
            ]
        },
    )

    assert response.status_code == 422
    assert service.batch_calls == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", "   "),
        ("text", "   "),
    ],
)
def test_blank_batch_item_fields_return_422(
    client: TestClient,
    field: str,
    value: str,
) -> None:
    service = FakeBatchOrchestrator()
    override_service(service)

    item = {
        "id": "block-0",
        "text": "Translate this.",
    }
    item[field] = value

    response = client.post(
        "/process-batch",
        json={
            "items": [item],
        },
    )

    assert response.status_code == 422
    assert service.batch_calls == []


def test_smart_batch_preserves_ids_and_order(
    client: TestClient,
) -> None:
    service = FakeBatchOrchestrator()
    override_service(service)

    response = client.post(
        "/process-batch",
        json={
            "items": [
                {
                    "id": "block-0",
                    "text": "First block.",
                },
                {
                    "id": "block-1",
                    "text": "Second block.",
                },
            ],
            "mode": "smart",
            "domain": "Web Development",
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "mode": "smart",
        "engine": "gemini-3.1-flash-lite",
        "validation_passed": True,
        "results": [
            {
                "id": "block-0",
                "translation": (
                    "Smart: First block."
                ),
            },
            {
                "id": "block-1",
                "translation": (
                    "Smart: Second block."
                ),
            },
        ],
    }

    assert service.smart_batch_calls == [
        (
            [
                "First block.",
                "Second block.",
            ],
            "Web Development",
        )
    ]

    assert service.batch_calls == []


def test_smart_batch_503_is_safe(
    client: TestClient,
) -> None:
    class UnavailableSmartOrchestrator(
        FakeBatchOrchestrator
    ):
        def translate_smart_many(
            self,
            texts: list[str],
            domain: str,
        ) -> list[dict[str, object]]:
            from backend.app.translation_service import (
                SmartModeUnavailableError,
            )

            raise SmartModeUnavailableError

    override_service(
        UnavailableSmartOrchestrator()
    )

    response = client.post(
        "/process-batch",
        json={
            "items": [
                {
                    "id": "block-0",
                    "text": "Translate this.",
                }
            ],
            "mode": "smart",
        },
    )

    assert response.status_code == 503

    assert response.json() == {
        "detail": (
            "Smart translation is not configured."
        )
    }


def test_smart_batch_validation_failure_is_safe(
    client: TestClient,
) -> None:
    class RejectedSmartOrchestrator(
        FakeBatchOrchestrator
    ):
        def translate_smart_many(
            self,
            texts: list[str],
            domain: str,
        ) -> list[dict[str, object]]:
            from backend.app.translation_service import (
                SmartTranslationRejectedError,
            )

            raise SmartTranslationRejectedError

    override_service(
        RejectedSmartOrchestrator()
    )

    response = client.post(
        "/process-batch",
        json={
            "items": [
                {
                    "id": "block-0",
                    "text": "Translate this.",
                }
            ],
            "mode": "smart",
        },
    )

    assert response.status_code == 502

    assert response.json() == {
        "detail": (
            "Smart translation output "
            "failed validation."
        )
    }


def test_smart_batch_provider_failure_is_safe(
    client: TestClient,
) -> None:
    class FailingSmartOrchestrator(
        FakeBatchOrchestrator
    ):
        def translate_smart_many(
            self,
            texts: list[str],
            domain: str,
        ) -> list[dict[str, object]]:
            from backend.app.translation_service import (
                SmartTranslationError,
            )

            raise SmartTranslationError(
                "sensitive provider failure"
            )

    override_service(
        FailingSmartOrchestrator()
    )

    response = client.post(
        "/process-batch",
        json={
            "items": [
                {
                    "id": "block-0",
                    "text": "Translate this.",
                }
            ],
            "mode": "smart",
        },
    )

    assert response.status_code == 502

    assert response.json() == {
        "detail": (
            "Smart translation service "
            "request failed."
        )
    }

    assert "sensitive" not in response.text


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (
            TerminologyError(
                "sensitive terminology path"
            ),
            500,
            (
                "Terminology configuration "
                "is unavailable."
            ),
        ),
        (
            TranslationServiceError(
                "sensitive model path"
            ),
            503,
            (
                "Basic translation service "
                "is unavailable."
            ),
        ),
    ],
)
def test_basic_batch_failures_use_safe_messages(
    client: TestClient,
    error: Exception,
    status_code: int,
    detail: str,
) -> None:
    class FailingBatchOrchestrator(
        FakeBatchOrchestrator
    ):
        def translate_basic_many(
            self,
            texts: list[str],
        ) -> list[dict[str, object]]:
            raise error

    override_service(
        FailingBatchOrchestrator()
    )

    response = client.post(
        "/process-batch",
        json={
            "items": [
                {
                    "id": "block-0",
                    "text": "Translate this.",
                }
            ]
        },
    )

    assert response.status_code == status_code
    assert response.json() == {
        "detail": detail
    }
    assert "sensitive" not in response.text
