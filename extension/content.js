console.log("VitouLens AI content script loaded.");

const {
  BLOCK_SELECTOR,
  EXCLUDED_SELECTOR,
  MIN_BLOCK_TEXT_LENGTH,
  normalizeBlockText,
  isCandidateText,
  buildBatchItems,
} = globalThis.VitouLensContentLogic;

const originalBlocks = new Map();


function getContentRoot() {
  const preferredRoots = [
    document.querySelector("article"),
    document.querySelector("[role='main']"),
    document.querySelector("main"),
  ];

  for (const root of preferredRoots) {
    const rootText = normalizeBlockText(
      root?.innerText
    );

    if (root && rootText.length >= 100) {
      return root;
    }
  }

  return document.body;
}


function isCandidateBlock(element) {
  if (!(element instanceof HTMLElement)) {
    return false;
  }

  if (element.closest(EXCLUDED_SELECTOR)) {
    return false;
  }

  if (
    element.classList.contains(
      "vitoulens-translated-block"
    )
  ) {
    return false;
  }

  const text = normalizeBlockText(
    element.innerText
  );

  if (!isCandidateText(text)) {
    return false;
  }

  const nestedBlocks = Array.from(
    element.querySelectorAll(BLOCK_SELECTOR)
  );

  const containsReadableNestedBlock = (
    nestedBlocks.some((child) => (
      normalizeBlockText(
        child.innerText
      ).length >= MIN_BLOCK_TEXT_LENGTH
    ))
  );

  return !containsReadableNestedBlock;
}


function getCandidateBlocks(
  root = getContentRoot(),
) {
  if (!root) {
    return [];
  }

  return Array.from(
    root.querySelectorAll(BLOCK_SELECTOR)
  ).filter(isCandidateBlock);
}


function createPageTranslationPlan() {
  const blocks = getCandidateBlocks();

  const items = buildBatchItems(
    blocks.map((block) => (
      normalizeBlockText(block.innerText)
    ))
  );

  return {
    blocks,
    items,
  };
}


function saveOriginalBlock(element) {
  if (originalBlocks.has(element)) {
    return;
  }

  originalBlocks.set(element, {
    innerHTML: element.innerHTML,
    lang: element.getAttribute("lang"),
  });
}


function saveOriginalBlocks(blocks) {
  for (const block of blocks) {
    saveOriginalBlock(block);
  }
}


function applyBlockTranslation(
  block,
  translation,
) {
  const translatedText = normalizeBlockText(
    translation
  );

  if (
    !(block instanceof HTMLElement)
    || !translatedText
  ) {
    throw new Error(
      "Translated page block is invalid."
    );
  }

  saveOriginalBlock(block);

  block.textContent = translatedText;
  block.setAttribute("lang", "km");

  block.classList.add(
    "vitoulens-translated-block"
  );

  block.classList.remove(
    "vitoulens-translating-block"
  );

  block.removeAttribute("aria-busy");
}


function restoreOriginalPage() {
  let restoredCount = 0;

  for (const [element, original] of originalBlocks) {
    if (!document.contains(element)) {
      continue;
    }

    element.innerHTML = original.innerHTML;

    if (original.lang === null) {
      element.removeAttribute("lang");
    } else {
      element.setAttribute(
        "lang",
        original.lang,
      );
    }

    element.classList.remove(
      "vitoulens-translated-block",
      "vitoulens-translating-block",
    );

    element.removeAttribute("aria-busy");

    restoredCount += 1;
  }

  originalBlocks.clear();

  return restoredCount;
}


chrome.runtime.onMessage.addListener(
  (message, _sender, sendResponse) => {
    if (message?.type === "GET_SELECTED_TEXT") {
      const selectedText = (
        window.getSelection()
          ?.toString()
          .trim()
        ?? ""
      );

      sendResponse({
        selectedText,
      });

      return;
    }

    if (
      message?.type
      === "RESTORE_ORIGINAL_PAGE"
    ) {
      sendResponse({
        success: true,
        restoredCount: restoreOriginalPage(),
      });
    }
  }
);
