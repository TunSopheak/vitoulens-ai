const test = require("node:test");
const assert = require("node:assert/strict");

const {
  BASIC_MODE,
  SMART_MODE,
  normalizeStoredMode,
  buildRequestPayload,
  extractTranslation,
  getHttpErrorMessage,
  getBackendUnavailableMessage,
  getInvalidBackendResponseMessage,
} = require("../popup-logic.js");


test("default mode is Basic", () => {
  assert.equal(normalizeStoredMode(undefined), BASIC_MODE);
});

test("valid stored Smart mode is preserved", () => {
  assert.equal(normalizeStoredMode(SMART_MODE), SMART_MODE);
});

test("invalid stored mode falls back to Basic", () => {
  assert.equal(normalizeStoredMode("unexpected"), BASIC_MODE);
});

test("Basic request payload is backward compatible", () => {
  assert.deepEqual(buildRequestPayload("Selected text", BASIC_MODE), {
    text: "Selected text",
    mode: "basic",
  });
});

test("Smart request payload includes the domain", () => {
  assert.deepEqual(buildRequestPayload("Selected text", SMART_MODE), {
    text: "Selected text",
    mode: "smart",
    domain: "Computer Science",
  });
});

test("Basic response uses processed_text", () => {
  assert.equal(
    extractTranslation({ processed_text: "Basic result" }, BASIC_MODE),
    "Basic result",
  );
});

test("Smart response uses translation", () => {
  assert.equal(
    extractTranslation({ translation: "Smart result" }, SMART_MODE),
    "Smart result",
  );
});

test("Smart 503 has a configuration message", () => {
  assert.equal(
    getHttpErrorMessage(SMART_MODE, 503),
    "Smart Mode is not configured or is currently unavailable.",
  );
});

test("Smart 502 has a validation or provider message", () => {
  assert.equal(
    getHttpErrorMessage(SMART_MODE, 502),
    "Smart translation failed validation or is temporarily unavailable.",
  );
});

test("backend unreachable has a local backend message", () => {
  assert.equal(
    getBackendUnavailableMessage(),
    "VitouLens local backend is not running.",
  );
});

test("malformed Basic success response is rejected", () => {
  assert.throws(
    () => extractTranslation({}, BASIC_MODE),
    /missing the expected result/,
  );

  assert.equal(
    getInvalidBackendResponseMessage(),
    "VitouLens received an invalid response from the local backend.",
  );
});

test("malformed Smart success response is rejected", () => {
  assert.throws(
    () => extractTranslation(
      { processed_text: "Basic-only result" },
      SMART_MODE,
    ),
    /missing the expected result/,
  );

  assert.equal(
    getInvalidBackendResponseMessage(),
    "VitouLens received an invalid response from the local backend.",
  );
});

test("invalid backend response message differs from network failure", () => {
  assert.equal(
    getBackendUnavailableMessage(),
    "VitouLens local backend is not running.",
  );

  assert.equal(
    getInvalidBackendResponseMessage(),
    "VitouLens received an invalid response from the local backend.",
  );

  assert.notEqual(
    getInvalidBackendResponseMessage(),
    getBackendUnavailableMessage(),
  );
});

test("Smart errors do not create a Basic fallback payload", () => {
  const payload = buildRequestPayload("Selected text", SMART_MODE);
  const message = getHttpErrorMessage(SMART_MODE, 502);

  assert.equal(payload.mode, SMART_MODE);
  assert.match(message, /^Smart translation/);
  assert.notEqual(payload.mode, BASIC_MODE);
});
