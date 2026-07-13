const test = require("node:test");
const assert = require("node:assert/strict");

const {
  BLOCK_SELECTOR,
  EXCLUDED_SELECTOR,
  normalizeBlockText,
  isCandidateText,
  buildBatchItems,
  mapBatchTranslations,
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


test("batch translations map by exact item order", () => {
  const items = buildBatchItems([
    "First English block.",
    "Second English block.",
  ]);

  assert.deepEqual(
    mapBatchTranslations(
      items,
      [
        {
          id: "block-0",
          translation: " ប្លុកទីមួយ។ ",
        },
        {
          id: "block-1",
          translation: "ប្លុកទីពីរ។",
        },
      ],
    ),
    [
      {
        id: "block-0",
        translation: "ប្លុកទីមួយ។",
      },
      {
        id: "block-1",
        translation: "ប្លុកទីពីរ។",
      },
    ],
  );
});


test("changed batch translation order is rejected", () => {
  const items = buildBatchItems([
    "First English block.",
    "Second English block.",
  ]);

  assert.throws(
    () => mapBatchTranslations(
      items,
      [
        {
          id: "block-1",
          translation: "ប្លុកទីពីរ។",
        },
        {
          id: "block-0",
          translation: "ប្លុកទីមួយ។",
        },
      ],
    ),
    /result is invalid/,
  );
});


test("blank batch translation is rejected", () => {
  const items = buildBatchItems([
    "First English block.",
  ]);

  assert.throws(
    () => mapBatchTranslations(
      items,
      [
        {
          id: "block-0",
          translation: "   ",
        },
      ],
    ),
    /result is invalid/,
  );
});


test("page batch cannot exceed 200 blocks", () => {
  assert.throws(
    () => buildBatchItems(
      Array.from(
        { length: 201 },
        (_, index) => (
          `English learning block ${index}.`
        ),
      )
    ),
    /batch is too large/,
  );
});
