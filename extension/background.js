importScripts("background-logic.js");

const {
  buildBatchPayload,
  extractBatchResponse,
  getBatchHttpErrorMessage,
  getBackendUnavailableMessage,
  getInvalidBackendResponseMessage,
  getInvalidBatchRequestMessage,
} = globalThis.VitouLensBackgroundLogic;

const BATCH_BACKEND_URL = (
  "http://127.0.0.1:8000/process-batch"
);

chrome.runtime.onMessage.addListener(
  (message, _sender, sendResponse) => {
    if (message?.type !== "TRANSLATE_BATCH") {
      return undefined;
    }

    void handleBatchTranslation(
      message,
      sendResponse,
    );

    return true;
  }
);

async function handleBatchTranslation(
  message,
  sendResponse,
) {
  let payload;

  try {
    payload = buildBatchPayload(
      message.items,
      message.mode,
    );
  } catch (_error) {
    sendResponse({
      ok: false,
      error: getInvalidBatchRequestMessage(),
    });

    return;
  }

  let response;

  try {
    response = await fetch(
      BATCH_BACKEND_URL,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      }
    );
  } catch (_error) {
    sendResponse({
      ok: false,
      error: getBackendUnavailableMessage(),
    });

    return;
  }

  if (!response.ok) {
    sendResponse({
      ok: false,
      error: getBatchHttpErrorMessage(
        payload.mode,
        response.status,
      ),
    });

    return;
  }

  try {
    const responseBody = await response.json();

    const result = extractBatchResponse(
      responseBody,
      payload.mode,
      payload.items,
    );

    sendResponse({
      ok: true,
      ...result,
    });
  } catch (_error) {
    sendResponse({
      ok: false,
      error: getInvalidBackendResponseMessage(),
    });
  }
}
