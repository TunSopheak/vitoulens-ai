(function initializeBackgroundLogic(root, factory) {
  const logic = factory();

  if (typeof module !== "undefined" && module.exports) {
    module.exports = logic;
  }

  root.VitouLensBackgroundLogic = logic;
})(globalThis, () => {
  const BASIC_MODE = "basic";
  const SMART_MODE = "smart";
  const VALID_MODES = new Set([
    BASIC_MODE,
    SMART_MODE,
  ]);

  const SMART_DOMAIN = "Computer Science";
  const MAX_BATCH_ITEMS = 200;
  const MAX_ID_LENGTH = 100;
  const MAX_TEXT_LENGTH = 5000;

  function validateMode(mode) {
    if (!VALID_MODES.has(mode)) {
      throw new Error(
        "Translation mode is invalid."
      );
    }

    return mode;
  }

  function normalizeBatchItems(items) {
    if (
      !Array.isArray(items)
      || items.length < 1
      || items.length > MAX_BATCH_ITEMS
    ) {
      throw new Error(
        "Batch items are invalid."
      );
    }

    const normalizedItems = [];
    const seenIds = new Set();

    for (const item of items) {
      const id = item?.id;
      const text = item?.text;

      if (
        typeof id !== "string"
        || !id.trim()
        || id.length > MAX_ID_LENGTH
      ) {
        throw new Error(
          "Batch item ID is invalid."
        );
      }

      if (seenIds.has(id)) {
        throw new Error(
          "Batch item IDs must be unique."
        );
      }

      if (
        typeof text !== "string"
        || !text.trim()
        || text.length > MAX_TEXT_LENGTH
      ) {
        throw new Error(
          "Batch item text is invalid."
        );
      }

      seenIds.add(id);

      normalizedItems.push({
        id,
        text,
      });
    }

    return normalizedItems;
  }

  function buildBatchPayload(items, mode) {
    const validMode = validateMode(mode);
    const normalizedItems = normalizeBatchItems(
      items
    );

    const payload = {
      items: normalizedItems,
      mode: validMode,
    };

    if (validMode === SMART_MODE) {
      payload.domain = SMART_DOMAIN;
    }

    return payload;
  }

  function extractBatchResponse(
    responseBody,
    mode,
    expectedItems,
  ) {
    const validMode = validateMode(mode);
    const normalizedItems = normalizeBatchItems(
      expectedItems
    );

    if (
      !responseBody
      || typeof responseBody !== "object"
      || responseBody.mode !== validMode
      || typeof responseBody.engine !== "string"
      || !responseBody.engine.trim()
      || !Array.isArray(responseBody.results)
      || (
        responseBody.results.length
        !== normalizedItems.length
      )
    ) {
      throw new Error(
        "Batch response is invalid."
      );
    }

    if (
      validMode === SMART_MODE
      && responseBody.validation_passed !== true
    ) {
      throw new Error(
        "Smart batch validation did not pass."
      );
    }

    const results = responseBody.results.map(
      (result, index) => {
        const expectedItem = normalizedItems[index];

        if (
          !result
          || typeof result !== "object"
          || result.id !== expectedItem.id
          || typeof result.translation !== "string"
          || !result.translation.trim()
        ) {
          throw new Error(
            "Batch result is invalid."
          );
        }

        return {
          id: result.id,
          translation: result.translation,
        };
      }
    );

    return {
      mode: validMode,
      engine: responseBody.engine,
      results,
      validationPassed: (
        validMode === SMART_MODE
          ? true
          : undefined
      ),
    };
  }

  function getBatchHttpErrorMessage(
    mode,
    status,
  ) {
    const validMode = validateMode(mode);

    if (
      validMode === SMART_MODE
      && status === 503
    ) {
      return (
        "Smart Mode is not configured "
        + "or is currently unavailable."
      );
    }

    if (
      validMode === SMART_MODE
      && status === 502
    ) {
      return (
        "Smart translation failed validation "
        + "or is temporarily unavailable."
      );
    }

    if (
      validMode === BASIC_MODE
      && status === 503
    ) {
      return (
        "Basic translation service "
        + "is currently unavailable."
      );
    }

    return "Translation failed. Please try again.";
  }

  function getBackendUnavailableMessage() {
    return (
      "VitouLens local backend is not running."
    );
  }

  function getInvalidBackendResponseMessage() {
    return (
      "VitouLens received an invalid response "
      + "from the local backend."
    );
  }

  function getInvalidBatchRequestMessage() {
    return "VitouLens received an invalid page translation request.";
  }

  return {
    BASIC_MODE,
    SMART_MODE,
    validateMode,
    normalizeBatchItems,
    buildBatchPayload,
    extractBatchResponse,
    getBatchHttpErrorMessage,
    getBackendUnavailableMessage,
    getInvalidBackendResponseMessage,
    getInvalidBatchRequestMessage,
  };
});
