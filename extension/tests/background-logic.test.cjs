const test = require("node:test");
const assert = require("node:assert/strict");

const {
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
} = require("../background-logic.js");


const ITEMS = [
  {
    id: "block-0",
    text: "First block.",
  },
  {
    id: "block-1",
    text: "Second block.",
  },
];


test("Basic batch payload preserves items", () => {
  assert.deepEqual(
    buildBatchPayload(ITEMS, BASIC_MODE),
    {
      items: ITEMS,
      mode: "basic",
    },
  );
});


test("Smart batch payload includes domain", () => {
  assert.deepEqual(
    buildBatchPayload(ITEMS, SMART_MODE),
    {
      items: ITEMS,
      mode: "smart",
      domain: "Computer Science",
    },
  );
});


test("invalid mode does not fall back to Basic", () => {
  assert.throws(
    () => validateMode("unexpected"),
    /mode is invalid/,
  );
});


test("duplicate batch IDs are rejected", () => {
  assert.throws(
    () => normalizeBatchItems([
      {
        id: "block-0",
        text: "First.",
      },
      {
        id: "block-0",
        text: "Second.",
      },
    ]),
    /unique/,
  );
});


test("Basic batch response preserves IDs and order", () => {
  const result = extractBatchResponse(
    {
      mode: "basic",
      engine: "test-basic",
      results: [
        {
          id: "block-0",
          translation: "Translation zero.",
        },
        {
          id: "block-1",
          translation: "Translation one.",
        },
      ],
    },
    BASIC_MODE,
    ITEMS,
  );

  assert.deepEqual(result.results, [
    {
      id: "block-0",
      translation: "Translation zero.",
    },
    {
      id: "block-1",
      translation: "Translation one.",
    },
  ]);
});


test("Smart response requires validation pass", () => {
  assert.throws(
    () => extractBatchResponse(
      {
        mode: "smart",
        engine: "gemini-test",
        validation_passed: false,
        results: [
          {
            id: "block-0",
            translation: "Translation zero.",
          },
          {
            id: "block-1",
            translation: "Translation one.",
          },
        ],
      },
      SMART_MODE,
      ITEMS,
    ),
    /validation did not pass/,
  );
});


test("changed result order is rejected", () => {
  assert.throws(
    () => extractBatchResponse(
      {
        mode: "basic",
        engine: "test-basic",
        results: [
          {
            id: "block-1",
            translation: "Translation one.",
          },
          {
            id: "block-0",
            translation: "Translation zero.",
          },
        ],
      },
      BASIC_MODE,
      ITEMS,
    ),
    /result is invalid/,
  );
});


test("Smart 503 has configuration message", () => {
  assert.equal(
    getBatchHttpErrorMessage(
      SMART_MODE,
      503,
    ),
    (
      "Smart Mode is not configured "
      + "or is currently unavailable."
    ),
  );
});


test("Smart 502 has validation message", () => {
  assert.equal(
    getBatchHttpErrorMessage(
      SMART_MODE,
      502,
    ),
    (
      "Smart translation failed validation "
      + "or is temporarily unavailable."
    ),
  );
});


test("Basic 503 has service message", () => {
  assert.equal(
    getBatchHttpErrorMessage(
      BASIC_MODE,
      503,
    ),
    (
      "Basic translation service "
      + "is currently unavailable."
    ),
  );
});


test("background messages remain distinct", () => {
  assert.notEqual(
    getBackendUnavailableMessage(),
    getInvalidBackendResponseMessage(),
  );

  assert.notEqual(
    getInvalidBatchRequestMessage(),
    getBackendUnavailableMessage(),
  );
});
