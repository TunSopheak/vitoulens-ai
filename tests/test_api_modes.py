from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app, get_translation_orchestrator
from backend.app.terminology import TerminologyError
from backend.app.translation_service import TranslationOrchestrator
from backend.app.translator import TranslationServiceError


BASIC_RESPONSE = {
    "original_text": "A browser sends a request.",
    "processed_text": "ការបកប្រែមូលដ្ឋាន។",
    "detected_terms": ["browser", "request"],
    "term_policies": [
        {"term": "browser", "action": "PREFERRED"},
        {"term": "request", "action": "KEEP"},
    ],
    "status": "translated",
}


class FakeOrchestrator:
    def __init__(self) -> None:
        self.basic_calls: list[str] = []
        self.smart_calls: list[tuple[str, str]] = []

    def translate_basic(self, text: str) -> dict[str, object]:
        self.basic_calls.append(text)
        return BASIC_RESPONSE

    def translate_smart(self, text: str, domain: str) -> dict[str, object]:
        self.smart_calls.append((text, domain))
        return {
            "original_text": text,
            "processed_text": "ការបកប្រែឆ្លាតវៃ។",
            "detected_terms": [],
            "term_policies": [],
            "status": "translated",
            "mode": "smart",
            "engine": "gemini-3.1-flash-lite",
            "validation_passed": True,
            "translation": "ការបកប្រែឆ្លាតវៃ។",
        }


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def override_service(service: Any) -> None:
    app.dependency_overrides[get_translation_orchestrator] = lambda: service


def test_request_without_mode_uses_basic_mode(client: TestClient) -> None:
    service = FakeOrchestrator()
    override_service(service)

    response = client.post(
        "/process-text",
        json={"text": "A browser sends a request."},
    )

    assert response.status_code == 200
    assert response.json() == BASIC_RESPONSE
    assert service.basic_calls == ["A browser sends a request."]
    assert service.smart_calls == []


def test_explicit_basic_mode(client: TestClient) -> None:
    service = FakeOrchestrator()
    override_service(service)

    response = client.post(
        "/process-text",
        json={"text": "A browser sends a request.", "mode": "basic"},
    )

    assert response.status_code == 200
    assert response.json() == BASIC_RESPONSE
    assert service.basic_calls == ["A browser sends a request."]


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (
            TerminologyError("sensitive terminology path"),
            500,
            "Terminology configuration is unavailable.",
        ),
        (
            TranslationServiceError("sensitive model path"),
            503,
            "Basic translation service is unavailable.",
        ),
    ],
)
def test_basic_failures_return_fixed_safe_messages(
    client: TestClient,
    error: Exception,
    status_code: int,
    detail: str,
) -> None:
    class FailingBasicOrchestrator(FakeOrchestrator):
        def translate_basic(self, text: str) -> dict[str, object]:
            raise error

    override_service(FailingBasicOrchestrator())

    response = client.post(
        "/process-text",
        json={"text": "Translate this."},
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}
    assert "sensitive" not in response.text


def test_successful_smart_mode(client: TestClient) -> None:
    calls: list[tuple[object, str, str]] = []

    def successful_translation(
        fake_client: object,
        text: str,
        domain: str,
        terms: list[Any],
    ) -> dict[str, Any]:
        calls.append((fake_client, text, domain))
        return {
            "output": "ការបកប្រែឆ្លាតវៃ។",
            "validation_passed": True,
            "detected_terms": [
                {
                    "term": "HTTP",
                    "action": "KEEP",
                    "preferred_khmer": None,
                }
            ],
            "raw_output": "internal raw output",
            "rejected_output": None,
            "protected_source": "internal protected source",
            "semantic_tags": ["internal tag"],
        }

    fake_client = object()
    service = TranslationOrchestrator(
        api_key_provider=lambda: "test-key",
        smart_client_factory=lambda _: fake_client,
        smart_translate=successful_translation,
    )
    override_service(service)

    response = client.post(
        "/process-text",
        json={
            "text": "A browser sends an HTTP request to a server.",
            "mode": "smart",
            "domain": "Web Development",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "smart"
    assert body["engine"] == "gemini-3.1-flash-lite"
    assert body["validation_passed"] is True
    assert body["translation"] == "ការបកប្រែឆ្លាតវៃ។"
    assert set(body) == {
        "original_text",
        "processed_text",
        "detected_terms",
        "term_policies",
        "status",
        "mode",
        "engine",
        "validation_passed",
        "translation",
    }
    assert calls == [
        (
            fake_client,
            "A browser sends an HTTP request to a server.",
            "Web Development",
        )
    ]


def test_missing_api_key_returns_503(client: TestClient) -> None:
    service = TranslationOrchestrator(api_key_provider=lambda: None)
    override_service(service)

    response = client.post(
        "/process-text",
        json={"text": "Translate this.", "mode": "smart"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Smart translation is not configured."
    }


def test_gemini_failure_returns_safe_502(client: TestClient) -> None:
    def fail_translation(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("sensitive provider failure")

    service = TranslationOrchestrator(
        api_key_provider=lambda: "test-key",
        smart_client_factory=lambda _: object(),
        smart_translate=fail_translation,
    )
    override_service(service)

    response = client.post(
        "/process-text",
        json={"text": "Translate this.", "mode": "smart"},
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Smart translation service request failed."
    }
    assert "sensitive" not in response.text


def test_smart_validation_rejection_returns_502(client: TestClient) -> None:
    def reject_translation(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {
            "output": None,
            "rejected_output": "invalid raw output",
            "validation_passed": False,
            "validation_issues": ["missing_tags"],
        }

    service = TranslationOrchestrator(
        api_key_provider=lambda: "test-key",
        smart_client_factory=lambda _: object(),
        smart_translate=reject_translation,
    )
    override_service(service)

    response = client.post(
        "/process-text",
        json={"text": "Translate this.", "mode": "smart"},
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Smart translation output failed validation."
    }
    assert "invalid raw output" not in response.text


def test_invalid_mode_returns_422(client: TestClient) -> None:
    service = FakeOrchestrator()
    override_service(service)

    response = client.post(
        "/process-text",
        json={"text": "Translate this.", "mode": "unknown"},
    )

    assert response.status_code == 422
    assert service.basic_calls == []
    assert service.smart_calls == []


def test_health_endpoint_still_works(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
