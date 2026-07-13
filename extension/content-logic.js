(function initializeContentLogic(root, factory) {
  const logic = factory();

  if (typeof module !== "undefined" && module.exports) {
    module.exports = logic;
  }

  root.VitouLensContentLogic = logic;
})(globalThis, () => {
  const BLOCK_SELECTOR = [
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "p",
    "li",
    "blockquote",
    "td",
    "th",
  ].join(",");

  const EXCLUDED_SELECTOR = [
    "nav",
    "header",
    "footer",
    "aside",
    "script",
    "style",
    "noscript",
    "pre",
    "button",
    "input",
    "textarea",
    "select",
    "[contenteditable='true']",
    ".vitoulens-page-controller",
    "[data-vitoulens-generated='true']",
  ].join(",");

  const MIN_BLOCK_TEXT_LENGTH = 3;
  const MAX_BLOCK_TEXT_LENGTH = 5000;
  const MAX_PAGE_BLOCKS = 200;

  function normalizeBlockText(value) {
    return typeof value === "string"
      ? value.trim()
      : "";
  }

  function isCandidateText(value) {
    const text = normalizeBlockText(value);

    return (
      text.length >= MIN_BLOCK_TEXT_LENGTH
      && text.length <= MAX_BLOCK_TEXT_LENGTH
      && /[A-Za-z]/.test(text)
    );
  }

  function buildBatchItems(texts) {
    if (!Array.isArray(texts)) {
      throw new Error(
        "Page block texts must be an array."
      );
    }

    if (texts.length > MAX_PAGE_BLOCKS) {
      throw new Error(
        "Page translation batch is too large."
      );
    }

    return texts.map((text, index) => {
      const normalizedText = normalizeBlockText(text);

      if (!isCandidateText(normalizedText)) {
        throw new Error(
          "Page block text is invalid."
        );
      }

      return {
        id: `block-${index}`,
        text: normalizedText,
      };
    });
  }

  function mapBatchTranslations(
    items,
    results,
  ) {
    if (
      !Array.isArray(items)
      || !Array.isArray(results)
      || items.length !== results.length
    ) {
      throw new Error(
        "Batch translation result count is invalid."
      );
    }

    return results.map((result, index) => {
      const expectedItem = items[index];

      const translation = normalizeBlockText(
        result?.translation
      );

      if (
        !expectedItem
        || typeof expectedItem.id !== "string"
        || !result
        || typeof result !== "object"
        || result.id !== expectedItem.id
        || !translation
      ) {
        throw new Error(
          "Batch translation result is invalid."
        );
      }

      return {
        id: result.id,
        translation,
      };
    });
  }

  return {
    BLOCK_SELECTOR,
    EXCLUDED_SELECTOR,
    MIN_BLOCK_TEXT_LENGTH,
    MAX_BLOCK_TEXT_LENGTH,
    MAX_PAGE_BLOCKS,
    normalizeBlockText,
    isCandidateText,
    buildBatchItems,
    mapBatchTranslations,
  };
});
