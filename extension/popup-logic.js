(function initializePopupLogic(root, factory) {
  const logic = factory();

  if (typeof module !== "undefined" && module.exports) {
    module.exports = logic;
  }

  root.VitouLensPopupLogic = logic;
})(globalThis, () => {
  const BASIC_MODE = "basic";
  const SMART_MODE = "smart";
  const VALID_MODES = new Set([BASIC_MODE, SMART_MODE]);
  const SMART_DOMAIN = "Computer Science";

  function normalizeStoredMode(mode) {
    return VALID_MODES.has(mode) ? mode : BASIC_MODE;
  }

  function buildRequestPayload(text, mode) {
    const validMode = normalizeStoredMode(mode);
    const payload = { text, mode: validMode };

    if (validMode === SMART_MODE) {
      payload.domain = SMART_DOMAIN;
    }

    return payload;
  }

  function extractTranslation(responseBody, mode) {
    const field = normalizeStoredMode(mode) === SMART_MODE
      ? "translation"
      : "processed_text";
    const translation = responseBody?.[field];

    if (typeof translation !== "string" || !translation.trim()) {
      throw new Error("Translation response is missing the expected result.");
    }

    return translation;
  }

  function getHttpErrorMessage(mode, status) {
    if (normalizeStoredMode(mode) === SMART_MODE && status === 503) {
      return "Smart Mode is not configured or is currently unavailable.";
    }

    if (normalizeStoredMode(mode) === SMART_MODE && status === 502) {
      return "Smart translation failed validation or is temporarily unavailable.";
    }

    return "Translation failed. Please try again.";
  }

  function getBackendUnavailableMessage() {
    return "VitouLens local backend is not running.";
  }

  function getInvalidBackendResponseMessage() {
    return "VitouLens received an invalid response from the local backend.";
  }

  return {
    BASIC_MODE,
    SMART_MODE,
    normalizeStoredMode,
    buildRequestPayload,
    extractTranslation,
    getHttpErrorMessage,
    getBackendUnavailableMessage,
    getInvalidBackendResponseMessage,
  };
});
