const test = require("node:test");
const assert = require("node:assert/strict");

const {
  BLOCK_SELECTOR,
  EXCLUDED_SELECTOR,
  normalizeBlockText,
  isCandidateText,
  buildBatchItems,
} = require("../content-logic.js");


test("block selector includes learning content elements", () => {
  for (const selector of [
    "h1",
    "p",
    "li",
    "blockquote",
    "td",
    "th",
  ]) {
    assert.match(
      BLOCK_SELECTOR,
      new RegExp(`(^|,)${selector}(,|$)`),
    );
  }
});


test("excluded selector protects navigation and editable content", () => {
  for (const selector of [
    "nav",
    "header",
    "footer",
    "pre",
    "button",
    "[contenteditable='true']",
  ]) {
    assert.ok(
      EXCLUDED_SELECTOR.includes(selector)
    );
  }
});


test("block text normalization trims outer whitespace", () => {
  assert.equal(
    normalizeBlockText(
      "  Learn FastAPI and SQL.  "
    ),
    "Learn FastAPI and SQL.",
  );
});


test("English learning text is a candidate", () => {
  assert.equal(
    isCandidateText(
      "The browser sends an HTTP request."
    ),
    true,
  );
});


test("Khmer-only text is not an English candidate", () => {
  assert.equal(
    isCandidateText(
      "នេះជាអត្ថបទភាសាខ្មែរ។"
    ),
    false,
  );
});


test("too short and oversized texts are rejected", () => {
  assert.equal(
    isCandidateText("AI"),
    false,
  );

  assert.equal(
    isCandidateText("A".repeat(5001)),
    false,
  );
});


test("batch items preserve text order with deterministic IDs", () => {
  assert.deepEqual(
    buildBatchItems([
      "First English block.",
      "Second English block.",
    ]),
    [
      {
        id: "block-0",
        text: "First English block.",
      },
      {
        id: "block-1",
        text: "Second English block.",
      },
    ],
  );
});
